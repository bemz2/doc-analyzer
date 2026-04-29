"""
LLM client module for interacting with OpenAI and Anthropic APIs.
Handles API calls, retries, rate limiting, and JSON response parsing.
"""
import json
import logging
import threading
import time
from collections import deque
from typing import Optional, Dict, Any, List, Deque
import openai
import anthropic

from app.config import settings
from app.schemas import ChunkAnalysis, Finding

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


OPENAI_COMPATIBLE_PROVIDER_DEFAULTS = {
    "custom": {
        "api_base": settings.custom_api_base,
        "api_key": settings.custom_api_key,
        "model": settings.custom_model,
    },
    "openrouter": {
        "api_base": "https://openrouter.ai/api/v1",
        "api_key": "",
        "model": "openai/gpt-4o-mini",
    },
}


class ProviderQuotaExceeded(RuntimeError):
    """Raised when a provider reports a hard quota limit that retries cannot fix."""


class SlidingWindowRateLimiter:
    """
    Sliding window rate limiter to prevent hitting provider RPM limits.
    Tracks timestamps of recent requests and enforces max_requests per window.
    """

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: float = 60.0,
        min_interval_seconds: float = 0.0,
    ):
        self.max_requests = max(1, max_requests)
        self.window_seconds = window_seconds
        self.min_interval_seconds = max(0.0, min_interval_seconds)
        self._lock = threading.Lock()
        self._timestamps: Deque[float] = deque()
        self._last_request_at: Optional[float] = None

    def acquire(self) -> None:
        """Block until a request slot is available without sending bursts."""
        while True:
            with self._lock:
                now = time.time()
                while self._timestamps and self._timestamps[0] <= now - self.window_seconds:
                    self._timestamps.popleft()

                wait_times = []
                if len(self._timestamps) >= self.max_requests:
                    wait_times.append(self.window_seconds - (now - self._timestamps[0]))

                if self._last_request_at is not None:
                    wait_times.append(self.min_interval_seconds - (now - self._last_request_at))

                wait_time = max(wait_times, default=0.0)
                if wait_time <= 0:
                    self._timestamps.append(now)
                    self._last_request_at = now
                    return

            logger.debug(f"Rate limit: sleeping {wait_time:.1f}s before next request")
            time.sleep(wait_time)

    def record_request(self) -> None:
        """Record a completed request timestamp."""
        with self._lock:
            self._timestamps.append(time.time())


class LLMClient:
    """Client for interacting with LLM APIs."""
    
    def __init__(
        self,
        provider: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        api_base: Optional[str] = None
    ):
        """Initialize LLM client based on configured provider."""
        self.provider = (provider or settings.llm_provider).strip().lower()

        if self.provider == "openai":
            openai_api_key = (api_key or settings.openai_api_key).strip()
            if self._is_missing_or_placeholder_key(openai_api_key):
                raise ValueError(
                    "OpenAI API key is not configured. Set OPENAI_API_KEY in .env "
                    "or enter a real key in model settings."
                )
            self.client = openai.OpenAI(api_key=openai_api_key, timeout=120.0, max_retries=0)
            self.model = (model or settings.openai_model).strip()
        elif self.provider == "anthropic":
            anthropic_api_key = (api_key or settings.anthropic_api_key).strip()
            if self._is_missing_or_placeholder_key(anthropic_api_key):
                raise ValueError(
                    "Anthropic API key is not configured. Set ANTHROPIC_API_KEY in .env "
                    "or enter a real key in model settings."
                )
            self.client = anthropic.Anthropic(api_key=anthropic_api_key, timeout=120.0, max_retries=0)
            self.model = (model or settings.anthropic_model).strip()
        else:
            provider_defaults = OPENAI_COMPATIBLE_PROVIDER_DEFAULTS.get(self.provider, {})
            custom_api_base = (api_base or provider_defaults.get("api_base") or "").strip()
            if not custom_api_base:
                raise ValueError(
                    f"API Base URL is not configured for provider '{self.provider}'. "
                    "Enter an OpenAI-compatible /v1 base URL in model settings."
                )
            custom_api_key = (api_key or provider_defaults.get("api_key") or "").strip()
            client_kwargs = {}
            if self.provider == "openrouter":
                client_kwargs["default_headers"] = {
                    "HTTP-Referer": "http://localhost",
                    "X-Title": "Document Analyzer",
                }
            self.client = openai.OpenAI(
                api_key=custom_api_key,
                base_url=custom_api_base,
                timeout=120.0,
                max_retries=0,
                **client_kwargs,
            )
            self.model = (model or provider_defaults.get("model") or "").strip()
            if not self.model:
                raise ValueError(f"Model is not configured for provider '{self.provider}'")
            logger.info(
                f"Initialized OpenAI-compatible LLM client '{self.provider}': "
                f"{custom_api_base} with model {self.model}"
            )

        self._rate_limiter = SlidingWindowRateLimiter(
            max_requests=settings.max_requests_per_minute,
            window_seconds=60.0,
            min_interval_seconds=max(
                settings.request_delay,
                60.0 / max(1, settings.max_requests_per_minute),
            ),
        )

    @staticmethod
    def _is_missing_or_placeholder_key(api_key: str) -> bool:
        """Detect missing keys and common placeholder values from examples."""
        if not api_key:
            return True

        normalized = api_key.strip().lower()
        placeholder_markers = (
            "your_",
            "your-",
            "your ",
            "api_key_here",
            "api-key-here",
            "sk-your",
            "sk-ваш",
            "ваш-ключ",
            "ваш_ключ",
        )
        return any(marker in normalized for marker in placeholder_markers)

    @staticmethod
    def _is_non_retryable_error(error: Exception) -> bool:
        """Avoid retrying authentication, permission, and bad model errors."""
        status_code = getattr(error, "status_code", None)
        # Don't retry auth, permission, not found errors
        # But DO retry rate limit errors (429)
        return status_code in {400, 401, 403, 404}
    
    @staticmethod
    def _is_rate_limit_error(error: Exception) -> tuple[bool, Optional[float]]:
        """Check if error is a rate limit error. Returns (is_ratelimit, retry_after_seconds)."""
        status_code = getattr(error, "status_code", None)
        if status_code != 429:
            return False, None

        retry_after = None
        response = getattr(error, "response", None)
        if response is not None:
            retry_after_header = response.headers.get("Retry-After") if hasattr(response, "headers") else None
            if retry_after_header:
                try:
                    retry_after = float(retry_after_header)
                except ValueError:
                    pass

        return True, retry_after

    @staticmethod
    def _is_quota_exhausted_error(error: Exception) -> bool:
        """Detect hard quota limits where retrying only burns more requests."""
        status_code = getattr(error, "status_code", None)
        if status_code != 429:
            return False

        message = str(error).lower()
        hard_limit_markers = (
            "free-models-per-day",
            "x-ratelimit-remaining': '0",
            '"x-ratelimit-remaining": "0',
            "quota exceeded",
            "daily limit",
        )
        return any(marker in message for marker in hard_limit_markers)

    def _format_llm_error(self, error: Exception) -> str:
        """Return a concise user-facing error while preserving provider context."""
        status_code = getattr(error, "status_code", None)
        message = str(error)

        if status_code == 401:
            return f"{self.provider}: authentication failed. Check the API key."
        if status_code == 403:
            return f"{self.provider}: access denied for model '{self.model}'."
        if status_code == 404:
            return f"{self.provider}: model or endpoint not found for '{self.model}'."
        if status_code == 400 and "model" in message.lower():
            return f"{self.provider}: model '{self.model}' is not available or does not support this request."
        if status_code == 429:
            if self._is_quota_exhausted_error(error):
                return (
                    f"{self.provider}: daily/free quota is exhausted for model '{self.model}'. "
                    "Switch to a paid/non-free model or wait for the provider quota reset."
                )
            return f"{self.provider}: rate limit exceeded. Too many requests. Please wait and try again."
        
        # Handle connection errors
        if "Connection" in message or "connection" in message.lower():
            if self.provider not in {"openai", "anthropic"}:
                return f"{self.provider}: Cannot connect to API Base URL. Check that the endpoint is reachable."
            return f"{self.provider}: Connection error. Check your internet connection."
        
        # Handle timeout errors
        if "timeout" in message.lower() or "timed out" in message.lower():
            return f"{self.provider}: Request timed out. The model may be taking too long to respond."

        return f"{self.provider}: {message}"
    
    def analyze_chunk(self, chunk_text: str, chunk_id: int, instructions: str) -> Optional[ChunkAnalysis]:
        """
        Analyze a document chunk using LLM.
        
        Args:
            chunk_text: Text content of the chunk
            chunk_id: Chunk identifier
            instructions: User instructions for analysis
            
        Returns:
            ChunkAnalysis object or None if failed
        """
        prompt = self._build_chunk_analysis_prompt(chunk_text, instructions)
        
        last_error = None
        for attempt in range(settings.max_retries):
            try:
                response = self._call_llm(prompt)
                analysis = self._parse_chunk_response(response, chunk_id)
                return analysis
            except Exception as e:
                last_error = e
                logger.warning(f"Attempt {attempt + 1} failed for chunk {chunk_id}: {str(e)}")
                
                if self._is_non_retryable_error(e):
                    raise RuntimeError(self._format_llm_error(e)) from e

                if self._is_quota_exhausted_error(e):
                    raise ProviderQuotaExceeded(self._format_llm_error(e)) from e
                
                is_ratelimit, retry_after = self._is_rate_limit_error(e)
                if is_ratelimit:
                    wait_time = retry_after or (settings.retry_delay * (attempt + 1))
                    logger.warning(f"Rate limit hit, waiting {wait_time} seconds before retry")
                    time.sleep(wait_time)
                elif attempt < settings.max_retries - 1:
                    time.sleep(settings.retry_delay)
                else:
                    logger.error(f"All retries failed for chunk {chunk_id}")
                    raise RuntimeError(self._format_llm_error(e)) from e
        
        raise RuntimeError(self._format_llm_error(last_error))
    
    def analyze_chunks_batch(
        self,
        chunks: list,
        instructions: str,
    ) -> List[ChunkAnalysis]:
        """
        Analyze a batch of chunks in a single LLM request.

        Args:
            chunks: List of dicts with keys `chunk_id` and `text`
            instructions: User instructions

        Returns:
            List of ChunkAnalysis, one per input chunk (in same order).
            If parsing fails, returns empty analyses for the whole batch.
        """
        if not chunks:
            return []

        if len(chunks) == 1:
            c = chunks[0]
            result = self.analyze_chunk(c["text"], c["chunk_id"], instructions)
            return [result] if result else [
                ChunkAnalysis(chunk_id=c["chunk_id"], summary="Анализ не удался", findings=[])
            ]

        prompt = self._build_batch_analysis_prompt(chunks, instructions)

        last_error = None
        for attempt in range(settings.max_retries):
            try:
                response = self._call_llm(prompt)
                analyses = self._parse_batch_response(response, chunks)
                return analyses
            except Exception as e:
                last_error = e
                logger.warning(
                    f"Batch attempt {attempt + 1} failed for chunks "
                    f"{[c['chunk_id'] for c in chunks]}: {e}"
                )

                if self._is_non_retryable_error(e):
                    raise RuntimeError(self._format_llm_error(e)) from e

                if self._is_quota_exhausted_error(e):
                    raise ProviderQuotaExceeded(self._format_llm_error(e)) from e

                is_ratelimit, retry_after = self._is_rate_limit_error(e)
                if is_ratelimit:
                    wait_time = retry_after or (settings.retry_delay * (attempt + 1))
                    logger.warning(f"Rate limit hit, waiting {wait_time}s before retry")
                    time.sleep(wait_time)
                elif attempt < settings.max_retries - 1:
                    time.sleep(settings.retry_delay)
                else:
                    logger.error(
                        f"All retries failed for batch "
                        f"{[c['chunk_id'] for c in chunks]}"
                    )
                    raise RuntimeError(self._format_llm_error(e)) from e

        raise RuntimeError(self._format_llm_error(last_error))

    def global_analysis(self, summaries: list, all_findings: list, instructions: str) -> Dict[str, Any]:
        """
        Perform global analysis of the entire document.
        
        Args:
            summaries: List of chunk summaries
            all_findings: List of all findings from chunks
            instructions: User instructions
            
        Returns:
            Dictionary with global analysis results
        """
        prompt = self._build_global_analysis_prompt(summaries, all_findings, instructions)
        
        last_error = None
        for attempt in range(settings.max_retries):
            try:
                response = self._call_llm(prompt)
                analysis = self._parse_global_response(response)
                return analysis
            except Exception as e:
                last_error = e
                logger.warning(f"Global analysis attempt {attempt + 1} failed: {str(e)}")
                
                if self._is_non_retryable_error(e):
                    raise RuntimeError(self._format_llm_error(e)) from e

                if self._is_quota_exhausted_error(e):
                    raise ProviderQuotaExceeded(self._format_llm_error(e)) from e
                
                is_ratelimit, retry_after = self._is_rate_limit_error(e)
                if is_ratelimit:
                    wait_time = retry_after or (settings.retry_delay * (attempt + 1))
                    logger.warning(f"Rate limit hit, waiting {wait_time} seconds before retry")
                    time.sleep(wait_time)
                elif attempt < settings.max_retries - 1:
                    time.sleep(settings.retry_delay)
                else:
                    logger.error("All retries failed for global analysis")
                    raise RuntimeError(self._format_llm_error(e)) from e
        
        raise RuntimeError(self._format_llm_error(last_error))
    
    def _call_llm(self, prompt: str) -> str:
        """
        Call the configured LLM API.
        
        Args:
            prompt: Prompt text
            
        Returns:
            Response text from LLM
        """
        self._rate_limiter.acquire()
        
        if self.provider != "anthropic":
            request_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a document analysis expert. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": settings.temperature,
                "max_tokens": settings.max_output_tokens,
            }
            if self.provider == "openai":
                request_params["response_format"] = {"type": "json_object"}

            logger.debug(f"Calling LLM with model: {self.model}")
            response = self.client.chat.completions.create(**request_params)
            logger.debug(f"LLM response received successfully")
            return response.choices[0].message.content
        
        elif self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=settings.max_output_tokens,
                temperature=settings.temperature,
                system="You are a document analysis expert. Always respond with valid JSON.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return response.content[0].text
        
        raise ValueError(f"Unsupported provider: {self.provider}")
    
    def _build_chunk_analysis_prompt(self, chunk_text: str, instructions: str) -> str:
        """Build prompt for chunk analysis."""
        return f"""Проанализируй следующий фрагмент документа согласно инструкциям пользователя.

ИНСТРУКЦИИ ПОЛЬЗОВАТЕЛЯ:
{instructions}

ФРАГМЕНТ ДОКУМЕНТА:
{chunk_text}

Верни результат СТРОГО в формате JSON:
{{
  "summary": "краткое содержание этого фрагмента (2-3 предложения)",
  "findings": [
    {{
      "issue_type": "style | grammar | structure | logic | compliance | other",
      "severity": "low | medium | high",
      "quote": "цитата из текста где найдена проблема",
      "problem": "описание проблемы",
      "recommendation": "рекомендация по исправлению"
    }}
  ]
}}

Если проблем не найдено, верни пустой массив findings.
Ответ должен быть валидным JSON."""
    
    def _build_global_analysis_prompt(self, summaries: list, all_findings: list, instructions: str) -> str:
        """Build prompt for global analysis."""
        summaries_text = "\n\n".join([f"Часть {i+1}: {s}" for i, s in enumerate(summaries)])
        findings_count = len(all_findings)
        
        return f"""Проведи глобальный анализ всего документа на основе summaries всех частей и найденных проблем.

ИНСТРУКЦИИ ПОЛЬЗОВАТЕЛЯ:
{instructions}

КРАТКОЕ СОДЕРЖАНИЕ ВСЕХ ЧАСТЕЙ:
{summaries_text}

ВСЕГО НАЙДЕНО ПРОБЛЕМ: {findings_count}

Верни результат СТРОГО в формате JSON:
{{
  "overall_summary": "общее резюме всего документа (3-5 предложений)",
  "document_structure_issues": ["проблема структуры 1", "проблема структуры 2"],
  "consistency_issues": ["проблема согласованности 1", "проблема согласованности 2"],
  "recommendations": ["рекомендация 1", "рекомендация 2", "рекомендация 3"]
}}

Ответ должен быть валидным JSON."""
    
    def _build_batch_analysis_prompt(self, chunks: List[dict], instructions: str) -> str:
        """Build a single prompt asking the LLM to analyze several chunks at once."""
        parts = []
        for c in chunks:
            parts.append(
                f"--- ФРАГМЕНТ chunk_id={c['chunk_id']} ---\n{c['text']}"
            )
        chunks_block = "\n\n".join(parts)
        ids = [c["chunk_id"] for c in chunks]

        return f"""Проанализируй несколько фрагментов документа согласно инструкциям пользователя.
Каждый фрагмент анализируй ОТДЕЛЬНО и верни результат для КАЖДОГО chunk_id.

ИНСТРУКЦИИ ПОЛЬЗОВАТЕЛЯ:
{instructions}

ФРАГМЕНТЫ ДОКУМЕНТА (всего {len(chunks)}):
{chunks_block}

Верни результат СТРОГО в формате JSON:
{{
  "results": [
    {{
      "chunk_id": <int>,
      "summary": "краткое содержание этого фрагмента (2-3 предложения)",
      "findings": [
        {{
          "issue_type": "style | grammar | structure | logic | compliance | other",
          "severity": "low | medium | high",
          "quote": "цитата из текста где найдена проблема",
          "problem": "описание проблемы",
          "recommendation": "рекомендация по исправлению"
        }}
      ]
    }}
  ]
}}

Массив results должен содержать РОВНО {len(chunks)} элементов с chunk_id из списка: {ids}.
Если в каком-то фрагменте проблем нет — верни пустой массив findings для этого chunk_id.
Ответ должен быть валидным JSON."""

    def _parse_batch_response(self, response: str, chunks: List[dict]) -> List[ChunkAnalysis]:
        """Parse batch LLM response into list of ChunkAnalysis, preserving input order."""
        expected_ids = [c["chunk_id"] for c in chunks]
        try:
            cleaned = self._clean_json_response(response)
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse batch JSON: {e}")
            logger.error(f"Response was: {response[:500]}")
            return [
                ChunkAnalysis(chunk_id=cid, summary="Ошибка парсинга ответа", findings=[])
                for cid in expected_ids
            ]

        # Accept either {"results": [...]} or a bare list
        raw_results = data.get("results") if isinstance(data, dict) else data
        if not isinstance(raw_results, list):
            logger.error(f"Batch response has no 'results' list: {str(data)[:300]}")
            return [
                ChunkAnalysis(chunk_id=cid, summary="Ошибка парсинга ответа", findings=[])
                for cid in expected_ids
            ]

        # Index returned items by chunk_id (fall back to positional mapping)
        by_id: Dict[int, dict] = {}
        positional: List[dict] = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            cid = item.get("chunk_id")
            if isinstance(cid, int):
                by_id[cid] = item
            positional.append(item)

        analyses: List[ChunkAnalysis] = []
        for idx, cid in enumerate(expected_ids):
            item = by_id.get(cid)
            if item is None and idx < len(positional):
                item = positional[idx]
            if item is None:
                analyses.append(ChunkAnalysis(
                    chunk_id=cid,
                    summary="Ответ LLM не содержит данных для этого фрагмента",
                    findings=[],
                ))
                continue

            findings = []
            for f in item.get("findings", []) or []:
                findings.append(Finding(
                    issue_type=f.get("issue_type", "other"),
                    severity=f.get("severity", "low"),
                    quote=f.get("quote", ""),
                    problem=f.get("problem", ""),
                    recommendation=f.get("recommendation", ""),
                ))
            analyses.append(ChunkAnalysis(
                chunk_id=cid,
                summary=item.get("summary", ""),
                findings=findings,
            ))
        return analyses

    def _parse_chunk_response(self, response: str, chunk_id: int) -> ChunkAnalysis:
        """Parse LLM response into ChunkAnalysis object."""
        try:
            # Clean response - remove markdown code blocks if present
            cleaned_response = self._clean_json_response(response)
            data = json.loads(cleaned_response)
            
            findings = []
            for f in data.get("findings", []):
                findings.append(Finding(
                    issue_type=f.get("issue_type", "other"),
                    severity=f.get("severity", "low"),
                    quote=f.get("quote", ""),
                    problem=f.get("problem", ""),
                    recommendation=f.get("recommendation", "")
                ))
            
            return ChunkAnalysis(
                chunk_id=chunk_id,
                summary=data.get("summary", ""),
                findings=findings
            )
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Response was: {response[:500]}")
            # Return empty analysis
            return ChunkAnalysis(
                chunk_id=chunk_id,
                summary="Ошибка парсинга ответа",
                findings=[]
            )
    
    def _parse_global_response(self, response: str) -> Dict[str, Any]:
        """Parse global analysis response."""
        try:
            # Clean response - remove markdown code blocks if present
            cleaned_response = self._clean_json_response(response)
            data = json.loads(cleaned_response)
            return {
                "overall_summary": data.get("overall_summary", ""),
                "document_structure_issues": data.get("document_structure_issues", []),
                "consistency_issues": data.get("consistency_issues", []),
                "recommendations": data.get("recommendations", [])
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse global analysis JSON: {e}")
            logger.error(f"Response was: {response[:500]}")
            return {
                "overall_summary": "Ошибка парсинга глобального анализа",
                "document_structure_issues": [],
                "consistency_issues": [],
                "recommendations": []
            }
    
    def _clean_json_response(self, response: str) -> str:
        """Remove markdown code blocks and clean JSON response."""
        if not response:
            return response
        
        # Remove markdown code blocks (```json ... ``` or ``` ... ```)
        response = response.strip()
        if response.startswith("```"):
            # Find the first newline after ```
            first_newline = response.find("\n")
            if first_newline != -1:
                response = response[first_newline + 1:]
            else:
                response = response[3:]  # Remove just ```
            
            # Remove trailing ```
            if response.endswith("```"):
                response = response[:-3]
        
        return response.strip()

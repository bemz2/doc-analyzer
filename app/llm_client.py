"""
LLM client module for interacting with OpenAI and Anthropic APIs.
Handles API calls, retries, and JSON response parsing.
"""
import json
import logging
import time
from typing import Optional, Dict, Any
import openai
import anthropic

from app.config import settings
from app.schemas import ChunkAnalysis, Finding

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


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
            self.client = openai.OpenAI(api_key=openai_api_key, timeout=120.0, max_retries=2)
            self.model = (model or settings.openai_model).strip()
        elif self.provider == "anthropic":
            anthropic_api_key = (api_key or settings.anthropic_api_key).strip()
            if self._is_missing_or_placeholder_key(anthropic_api_key):
                raise ValueError(
                    "Anthropic API key is not configured. Set ANTHROPIC_API_KEY in .env "
                    "or enter a real key in model settings."
                )
            self.client = anthropic.Anthropic(api_key=anthropic_api_key, timeout=120.0, max_retries=2)
            self.model = (model or settings.anthropic_model).strip()
        elif self.provider == "custom":
            custom_api_base = (api_base or settings.custom_api_base).strip()
            if not custom_api_base:
                raise ValueError("CUSTOM_API_BASE not set in environment")
            custom_api_key = (api_key or settings.custom_api_key).strip()
            self.client = openai.OpenAI(
                api_key=custom_api_key,
                base_url=custom_api_base,
                timeout=120.0,
                max_retries=2
            )
            self.model = (model or settings.custom_model).strip()
            logger.info(f"Initialized custom LLM client: {custom_api_base} with model {self.model}")
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

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
        return status_code in {400, 401, 403, 404}

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
        
        # Handle connection errors
        if "Connection" in message or "connection" in message.lower():
            if self.provider == "custom":
                return f"{self.provider}: Cannot connect to local server. Check if the server is running and accessible."
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
                if attempt < settings.max_retries - 1:
                    time.sleep(settings.retry_delay)
                else:
                    logger.error(f"All retries failed for chunk {chunk_id}")
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
                if attempt < settings.max_retries - 1:
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
        if self.provider == "openai" or self.provider == "custom":
            request_params = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": "You are a document analysis expert. Always respond with valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": settings.temperature,
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
                max_tokens=4096,
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

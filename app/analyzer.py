"""
Document analyzer module - orchestrates the complete analysis pipeline.
Coordinates document loading, chunking, LLM analysis, and report generation.
"""
import logging
from typing import List, Optional, Dict, Any

from app.config import settings
from app.document_loader import DocumentLoader
from app.chunker import DocumentChunker
from app.llm_client import LLMClient, ProviderQuotaExceeded
from app.schemas import AnalysisReport, ChunkAnalysis, GlobalAnalysis
from app.token_calculator import get_model_context_window

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


class DocumentAnalyzer:
    """Orchestrates the complete document analysis pipeline."""
    
    def __init__(self, file_path: str, llm_config: Optional[Dict[str, Any]] = None):
        """
        Initialize document analyzer.
        
        Args:
            file_path: Path to the document file
            llm_config: Optional runtime LLM settings from API/UI
        """
        self.file_path = file_path
        self.loader = DocumentLoader(file_path)
        self.chunker = DocumentChunker()
        self.llm_client = LLMClient(**(llm_config or {}))
        
    def analyze(self, instructions: str, progress_callback=None) -> AnalysisReport:
        """
        Perform complete document analysis.
        
        Args:
            instructions: User instructions for analysis
            progress_callback: Optional callback function for progress updates
            
        Returns:
            AnalysisReport object with complete analysis results
        """
        logger.info(f"Starting analysis of document: {self.file_path}")
        
        # Step 1: Validate and load document
        if progress_callback:
            progress_callback("Загрузка документа...", 0)
        
        is_valid, error = self.loader.validate_file()
        if not is_valid:
            raise ValueError(f"Document validation failed: {error}")
        
        # Step 2: Extract text
        if progress_callback:
            progress_callback("Извлечение текста...", 10)
        
        paragraphs = self.loader.extract_text()
        logger.info(f"Extracted {len(paragraphs)} paragraphs")
        
        # Step 3: Split into chunks
        if progress_callback:
            progress_callback("Разбиение на части...", 20)
        
        chunks = self.chunker.chunk_paragraphs(paragraphs)
        logger.info(f"Created {len(chunks)} chunks")
        
        # Step 4: Analyze each chunk
        if progress_callback:
            progress_callback(f"Анализ частей (0/{len(chunks)})...", 30, 0, len(chunks))
        
        chunk_analyses = self._analyze_chunks(chunks, instructions, progress_callback)
        
        # Step 5: Global analysis
        if progress_callback:
            progress_callback("Глобальный анализ...", 90)
        
        global_analysis = self._perform_global_analysis(chunk_analyses, instructions)
        
        # Step 6: Create report
        if progress_callback:
            progress_callback("Формирование отчёта...", 95)
        
        total_findings = sum(len(ca.findings) for ca in chunk_analyses)
        
        report = AnalysisReport(
            document_name=self.file_path.split('/')[-1],
            total_chunks=len(chunks),
            total_findings=total_findings,
            chunk_analyses=chunk_analyses,
            global_analysis=global_analysis
        )
        
        if progress_callback:
            progress_callback("Готово!", 100)
        
        logger.info(f"Analysis complete. Found {total_findings} issues across {len(chunks)} chunks")
        return report
    
    def _analyze_chunks(self, chunks: List[dict], instructions: str, progress_callback=None) -> List[ChunkAnalysis]:
        """
        Analyze chunks sequentially in batches.

        Batching groups `settings.batch_size` chunks into a single LLM request,
        which drastically reduces the number of calls (and thus rate-limit hits)
        for documents with many small chunks.

        Args:
            chunks: List of chunk dictionaries
            instructions: User instructions
            progress_callback: Optional progress callback

        Returns:
            List of ChunkAnalysis objects (sorted by chunk_id)
        """
        chunk_analyses: List[ChunkAnalysis] = []
        failed_errors: List[str] = []
        total = len(chunks)
        if total == 0:
            return chunk_analyses

        batch_size = self._get_effective_batch_size()
        batches = self._build_batches(chunks, instructions, batch_size)
        logger.info(
            f"Analyzing {total} chunks in {len(batches)} batch(es) of up to {batch_size}"
        )

        completed = 0
        for batch_number, batch in enumerate(batches, start=1):
            batch_ids = [c["chunk_id"] for c in batch]
            if progress_callback:
                first_chunk = completed + 1
                last_chunk = min(completed + len(batch), total)
                progress = 30 + int((completed / total) * 60)
                progress_callback(
                    f"Запрос к модели: части {first_chunk}-{last_chunk} из {total} "
                    f"(батч {batch_number}/{len(batches)})...",
                    progress,
                    completed,
                    total,
                )
            logger.info(
                f"Sending batch {batch_number}/{len(batches)} to LLM "
                f"for chunk ids {batch_ids}"
            )
            try:
                results = self.llm_client.analyze_chunks_batch(batch, instructions)
                logger.info(
                    f"Received LLM response for batch {batch_number}/{len(batches)} "
                    f"with chunk ids {batch_ids}"
                )
                # Ensure we have one result per chunk in batch
                results_by_id = {r.chunk_id: r for r in results}
                for chunk in batch:
                    cid = chunk["chunk_id"]
                    analysis = results_by_id.get(cid)
                    if analysis is None:
                        analysis = ChunkAnalysis(
                            chunk_id=cid,
                            summary="Анализ не удался",
                            findings=[],
                        )
                    chunk_analyses.append(analysis)
            except Exception as e:
                logger.error(f"Error analyzing batch {batch_ids}: {e}")
                if isinstance(e, ProviderQuotaExceeded):
                    raise
                failed_errors.append(str(e))
                for chunk in batch:
                    chunk_analyses.append(ChunkAnalysis(
                        chunk_id=chunk["chunk_id"],
                        summary=f"Ошибка: {e}",
                        findings=[],
                    ))

            completed += len(batch)
            if progress_callback:
                progress = 30 + int((completed / total) * 60)
                progress_callback(
                    f"Анализ частей ({completed}/{total})...",
                    progress,
                    completed,
                    total,
                )

        chunk_analyses.sort(key=lambda x: x.chunk_id)

        # Fail hard only if every batch errored out.
        if failed_errors and len(failed_errors) == len(batches):
            raise RuntimeError(
                f"All document batches failed to analyze. First error: {failed_errors[0]}"
            )

        return chunk_analyses

    def _get_effective_batch_size(self) -> int:
        """Return configured batch size, with conservative handling for fragile free models."""
        configured_batch_size = max(1, int(settings.batch_size))
        provider = getattr(self.llm_client, "provider", "")
        model = getattr(self.llm_client, "model", "")
        if provider == "openrouter" and (":free" in model or "reasoning" in model.lower()):
            return 1
        return configured_batch_size

    def _get_batch_token_budget(self, instructions: str) -> int:
        """
        Estimate a safe input-token budget for one LLM request.

        The chunker already limits a single chunk, but batching needs a second
        guard so several chunks do not exceed the selected model context.
        """
        if settings.batch_max_input_tokens > 0:
            return max(1, int(settings.batch_max_input_tokens))

        context_window = get_model_context_window(
            self.llm_client.model,
            fallback=max(settings.chunk_size * self._get_effective_batch_size(), settings.chunk_size),
        )
        prompt_overhead = self.chunker.count_tokens(instructions) + 2000
        available = context_window - settings.max_output_tokens - prompt_overhead
        return max(1, int(available * 0.85))

    def _build_batches(self, chunks: List[dict], instructions: str, batch_size: int) -> List[List[dict]]:
        """Group chunks by max count and estimated prompt token budget."""
        token_budget = self._get_batch_token_budget(instructions)
        batches: List[List[dict]] = []
        current_batch: List[dict] = []
        current_tokens = 0

        for chunk in chunks:
            chunk_tokens = int(chunk.get("token_count") or self.chunker.count_tokens(chunk.get("text", "")))
            would_exceed_count = len(current_batch) >= batch_size
            would_exceed_tokens = current_batch and current_tokens + chunk_tokens > token_budget

            if would_exceed_count or would_exceed_tokens:
                batches.append(current_batch)
                current_batch = []
                current_tokens = 0

            current_batch.append(chunk)
            current_tokens += chunk_tokens

        if current_batch:
            batches.append(current_batch)

        return batches
    
    def _perform_global_analysis(self, chunk_analyses: List[ChunkAnalysis], instructions: str) -> Optional[GlobalAnalysis]:
        """
        Perform global analysis of the entire document.
        
        Args:
            chunk_analyses: List of chunk analysis results
            instructions: User instructions
            
        Returns:
            GlobalAnalysis object or None
        """
        try:
            # Extract summaries and findings
            summaries = [ca.summary for ca in chunk_analyses]
            all_findings = []
            for ca in chunk_analyses:
                all_findings.extend(ca.findings)
            
            # Call LLM for global analysis
            global_data = self.llm_client.global_analysis(summaries, all_findings, instructions)
            
            return GlobalAnalysis(
                overall_summary=global_data.get("overall_summary", ""),
                document_structure_issues=global_data.get("document_structure_issues", []),
                consistency_issues=global_data.get("consistency_issues", []),
                recommendations=global_data.get("recommendations", [])
            )
        except Exception as e:
            logger.error(f"Global analysis failed: {e}")
            raise RuntimeError(f"Global analysis failed: {e}") from e

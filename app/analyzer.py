"""
Document analyzer module - orchestrates the complete analysis pipeline.
Coordinates document loading, chunking, LLM analysis, and report generation.
"""
import logging
from typing import List, Optional, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.config import settings
from app.document_loader import DocumentLoader
from app.chunker import DocumentChunker
from app.llm_client import LLMClient
from app.schemas import AnalysisReport, ChunkAnalysis, GlobalAnalysis

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
            progress_callback(f"Анализ частей (0/{len(chunks)})...", 30)
        
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
        Analyze all chunks in parallel.
        
        Args:
            chunks: List of chunk dictionaries
            instructions: User instructions
            progress_callback: Optional progress callback
            
        Returns:
            List of ChunkAnalysis objects
        """
        chunk_analyses = []
        failed_errors = []
        completed = 0
        total = len(chunks)
        
        # Use ThreadPoolExecutor for parallel processing
        with ThreadPoolExecutor(max_workers=5) as executor:
            # Submit all tasks
            future_to_chunk = {
                executor.submit(
                    self.llm_client.analyze_chunk,
                    chunk["text"],
                    chunk["chunk_id"],
                    instructions
                ): chunk for chunk in chunks
            }
            
            # Process completed tasks
            for future in as_completed(future_to_chunk):
                chunk = future_to_chunk[future]
                try:
                    analysis = future.result()
                    if analysis:
                        chunk_analyses.append(analysis)
                    else:
                        # Create empty analysis for failed chunks
                        chunk_analyses.append(ChunkAnalysis(
                            chunk_id=chunk["chunk_id"],
                            summary="Анализ не удался",
                            findings=[]
                        ))
                except Exception as e:
                    logger.error(f"Error analyzing chunk {chunk['chunk_id']}: {e}")
                    failed_errors.append(str(e))
                    chunk_analyses.append(ChunkAnalysis(
                        chunk_id=chunk["chunk_id"],
                        summary=f"Ошибка: {str(e)}",
                        findings=[]
                    ))
                
                completed += 1
                if progress_callback:
                    progress = 30 + int((completed / total) * 60)
                    progress_callback(f"Анализ частей ({completed}/{total})...", progress)
        
        # Sort by chunk_id
        chunk_analyses.sort(key=lambda x: x.chunk_id)

        if failed_errors and len(failed_errors) == total:
            raise RuntimeError(f"All document chunks failed to analyze. First error: {failed_errors[0]}")

        return chunk_analyses
    
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

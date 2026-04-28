"""
Text chunking module for splitting large documents into manageable pieces.
Preserves paragraph boundaries and maintains context with overlap.
"""
import logging
from typing import List
import tiktoken

from app.config import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


class DocumentChunker:
    """Splits document text into chunks for LLM processing."""
    
    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        """
        Initialize document chunker.
        
        Args:
            chunk_size: Maximum tokens per chunk
            chunk_overlap: Number of overlapping tokens between chunks
        """
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        self.encoding = tiktoken.get_encoding("cl100k_base")
        
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Input text
            
        Returns:
            Number of tokens
        """
        return len(self.encoding.encode(text))
    
    def chunk_paragraphs(self, paragraphs: List[str]) -> List[dict]:
        """
        Split paragraphs into chunks respecting token limits.
        
        Args:
            paragraphs: List of paragraph strings
            
        Returns:
            List of chunk dictionaries with id, text, and metadata
        """
        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_id = 1
        
        for i, para in enumerate(paragraphs):
            para_tokens = self.count_tokens(para)
            
            # If single paragraph exceeds chunk size, split it
            if para_tokens > self.chunk_size:
                # Save current chunk if not empty
                if current_chunk:
                    chunks.append({
                        "chunk_id": chunk_id,
                        "text": "\n\n".join(current_chunk),
                        "paragraph_start": i - len(current_chunk),
                        "paragraph_end": i - 1,
                        "token_count": current_tokens
                    })
                    chunk_id += 1
                    current_chunk = []
                    current_tokens = 0
                
                # Split large paragraph into sentences
                sub_chunks = self._split_large_paragraph(para, chunk_id)
                chunks.extend(sub_chunks)
                chunk_id += len(sub_chunks)
                continue
            
            # Check if adding this paragraph exceeds chunk size
            if current_tokens + para_tokens > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": "\n\n".join(current_chunk),
                    "paragraph_start": i - len(current_chunk),
                    "paragraph_end": i - 1,
                    "token_count": current_tokens
                })
                chunk_id += 1
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk)
                current_chunk = [overlap_text, para] if overlap_text else [para]
                current_tokens = self.count_tokens("\n\n".join(current_chunk))
            else:
                # Add paragraph to current chunk
                current_chunk.append(para)
                current_tokens += para_tokens
        
        # Add final chunk
        if current_chunk:
            chunks.append({
                "chunk_id": chunk_id,
                "text": "\n\n".join(current_chunk),
                "paragraph_start": len(paragraphs) - len(current_chunk),
                "paragraph_end": len(paragraphs) - 1,
                "token_count": current_tokens
            })
        
        logger.info(f"Created {len(chunks)} chunks from {len(paragraphs)} paragraphs")
        return chunks
    
    def _split_large_paragraph(self, paragraph: str, start_id: int) -> List[dict]:
        """
        Split a large paragraph into smaller chunks by sentences.
        
        Args:
            paragraph: Large paragraph text
            start_id: Starting chunk ID
            
        Returns:
            List of chunk dictionaries
        """
        # Simple sentence splitting (can be improved with nltk)
        sentences = []
        for sent in paragraph.replace('! ', '!|').replace('? ', '?|').replace('. ', '.|').split('|'):
            sent = sent.strip()
            if sent:
                sentences.append(sent)
        
        chunks = []
        current_chunk = []
        current_tokens = 0
        chunk_id = start_id
        
        for sent in sentences:
            sent_tokens = self.count_tokens(sent)
            
            if current_tokens + sent_tokens > self.chunk_size and current_chunk:
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": " ".join(current_chunk),
                    "paragraph_start": -1,
                    "paragraph_end": -1,
                    "token_count": current_tokens
                })
                chunk_id += 1
                current_chunk = [sent]
                current_tokens = sent_tokens
            else:
                current_chunk.append(sent)
                current_tokens += sent_tokens
        
        if current_chunk:
            chunks.append({
                "chunk_id": chunk_id,
                "text": " ".join(current_chunk),
                "paragraph_start": -1,
                "paragraph_end": -1,
                "token_count": current_tokens
            })
        
        return chunks
    
    def _get_overlap_text(self, current_chunk: List[str]) -> str:
        """
        Get overlap text from end of current chunk.
        
        Args:
            current_chunk: List of paragraphs in current chunk
            
        Returns:
            Overlap text or empty string
        """
        if not current_chunk:
            return ""
        
        # Take last paragraph(s) for overlap
        overlap_paras = []
        overlap_tokens = 0
        
        for para in reversed(current_chunk):
            para_tokens = self.count_tokens(para)
            if overlap_tokens + para_tokens <= self.chunk_overlap:
                overlap_paras.insert(0, para)
                overlap_tokens += para_tokens
            else:
                break
        
        return "\n\n".join(overlap_paras) if overlap_paras else ""

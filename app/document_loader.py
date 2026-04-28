"""
Document loader module for extracting text from .docx files.
Handles file validation, text extraction, and paragraph preservation.
"""
import os
import logging
from typing import List, Tuple
from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from app.config import settings

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


class DocumentLoader:
    """Handles loading and text extraction from Word documents."""
    
    def __init__(self, file_path: str):
        """
        Initialize document loader.
        
        Args:
            file_path: Path to the .docx file
        """
        self.file_path = file_path
        self.document = None
        
    def validate_file(self) -> Tuple[bool, str]:
        """
        Validate the document file.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not os.path.exists(self.file_path):
            return False, "File does not exist"
        
        if not self.file_path.endswith('.docx'):
            return False, "File must be a .docx document"
        
        file_size_mb = os.path.getsize(self.file_path) / (1024 * 1024)
        if file_size_mb > settings.max_file_size_mb:
            return False, f"File size exceeds {settings.max_file_size_mb}MB limit"
        
        try:
            self.document = Document(self.file_path)
            return True, ""
        except Exception as e:
            return False, f"Failed to open document: {str(e)}"
    
    def extract_text(self) -> List[str]:
        """
        Extract text from document preserving paragraph structure.
        
        Returns:
            List of paragraphs as strings
        """
        if not self.document:
            is_valid, error = self.validate_file()
            if not is_valid:
                raise ValueError(error)
        
        paragraphs = []
        
        for element in self.document.element.body:
            if isinstance(element, CT_P):
                para = Paragraph(element, self.document)
                text = para.text.strip()
                if text:
                    paragraphs.append(text)
            elif isinstance(element, CT_Tbl):
                table = Table(element, self.document)
                table_text = self._extract_table_text(table)
                if table_text:
                    paragraphs.append(table_text)
        
        logger.info(f"Extracted {len(paragraphs)} paragraphs from document")
        return paragraphs
    
    def _extract_table_text(self, table: Table) -> str:
        """
        Extract text from a table.
        
        Args:
            table: Document table object
            
        Returns:
            Formatted table text
        """
        table_data = []
        for row in table.rows:
            row_data = []
            for cell in row.cells:
                cell_text = cell.text.strip()
                if cell_text:
                    row_data.append(cell_text)
            if row_data:
                table_data.append(" | ".join(row_data))
        
        return "\n".join(table_data)
    
    def get_document_stats(self) -> dict:
        """
        Get basic statistics about the document.
        
        Returns:
            Dictionary with document statistics
        """
        if not self.document:
            is_valid, error = self.validate_file()
            if not is_valid:
                raise ValueError(error)
        
        paragraphs = self.extract_text()
        total_text = " ".join(paragraphs)
        
        return {
            "total_paragraphs": len(paragraphs),
            "total_characters": len(total_text),
            "total_words": len(total_text.split()),
            "file_size_mb": round(os.path.getsize(self.file_path) / (1024 * 1024), 2)
        }

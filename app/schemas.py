"""
Data schemas for document analyzer application.
Defines Pydantic models for request/response validation and data structures.
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class Finding(BaseModel):
    """Represents a single issue found in the document."""
    issue_type: Literal["style", "grammar", "structure", "logic", "compliance", "other"]
    severity: Literal["low", "medium", "high"]
    quote: str = Field(..., description="Fragment of text where issue was found")
    problem: str = Field(..., description="Description of the problem")
    recommendation: str = Field(..., description="Suggested fix or improvement")


class ChunkAnalysis(BaseModel):
    """Analysis result for a single document chunk."""
    chunk_id: int
    summary: str = Field(..., description="Brief summary of the chunk content")
    findings: List[Finding] = Field(default_factory=list)


class GlobalAnalysis(BaseModel):
    """Global analysis of the entire document."""
    overall_summary: str
    document_structure_issues: List[str] = Field(default_factory=list)
    consistency_issues: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class AnalysisReport(BaseModel):
    """Complete analysis report for the document."""
    document_name: str
    total_chunks: int
    total_findings: int
    chunk_analyses: List[ChunkAnalysis]
    global_analysis: Optional[GlobalAnalysis] = None
    
    def get_findings_by_severity(self, severity: str) -> List[Finding]:
        """Get all findings filtered by severity level."""
        findings = []
        for chunk in self.chunk_analyses:
            findings.extend([f for f in chunk.findings if f.severity == severity])
        return findings
    
    def get_findings_by_type(self, issue_type: str) -> List[Finding]:
        """Get all findings filtered by issue type."""
        findings = []
        for chunk in self.chunk_analyses:
            findings.extend([f for f in chunk.findings if f.issue_type == issue_type])
        return findings


class AnalyzeRequest(BaseModel):
    """Request model for document analysis."""
    instructions: str = Field(..., description="User instructions for document analysis")
    file_name: str = Field(..., description="Name of the uploaded file")


class AnalyzeResponse(BaseModel):
    """Response model for document analysis."""
    status: str
    message: str
    report: Optional[AnalysisReport] = None
    report_id: Optional[str] = None

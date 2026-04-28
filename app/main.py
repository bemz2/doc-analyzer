"""
FastAPI main application module.
Provides REST API endpoints for document upload and analysis.
"""
import os
import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import settings
from app.analyzer import DocumentAnalyzer
from app.report_generator import ReportGenerator
from app.schemas import AnalysisReport
from app.token_calculator import get_all_model_estimates, get_model_context_window, calculate_cost
from app.database import (
    save_settings, get_settings, save_analysis_history, get_analysis_history,
    save_instruction_template, get_instruction_templates, update_instruction_template,
    increment_template_use_count, delete_instruction_template
)

logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


class SettingsRequest(BaseModel):
    provider: str
    api_key: Optional[str] = ""
    model: str
    api_base: Optional[str] = None


class InstructionTemplateRequest(BaseModel):
    name: str
    content: str
    description: Optional[str] = ""
    category: Optional[str] = "custom"


class InstructionTemplateUpdateRequest(BaseModel):
    name: Optional[str] = None
    content: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_favorite: Optional[bool] = None


app = FastAPI(
    title="Document Analyzer API",
    description="API for analyzing large Word documents using LLM",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
Path(settings.upload_dir).mkdir(exist_ok=True)
Path(settings.report_dir).mkdir(exist_ok=True)

# Store analysis results in memory (for demo purposes)
analysis_cache = {}


def get_default_llm_settings() -> dict:
    """Return environment-backed defaults when user settings are not saved yet."""
    provider = settings.llm_provider
    if provider == "custom":
        return {
            "provider": "custom",
            "api_key": settings.custom_api_key,
            "model": settings.custom_model,
            "api_base": settings.custom_api_base,
        }
    if provider == "anthropic":
        return {
            "provider": "anthropic",
            "api_key": settings.anthropic_api_key,
            "model": settings.anthropic_model,
            "api_base": None,
        }
    return {
        "provider": "openai",
        "api_key": settings.openai_api_key,
        "model": settings.openai_model,
        "api_base": None,
    }


def get_effective_llm_settings() -> dict:
    """Load user settings from DB, falling back to environment defaults."""
    saved_settings = get_settings()
    if saved_settings:
        raw_settings = saved_settings
    else:
        raw_settings = get_default_llm_settings()

    return {
        "provider": raw_settings.get("provider"),
        "api_key": raw_settings.get("api_key") or "",
        "model": raw_settings.get("model"),
        "api_base": raw_settings.get("api_base"),
    }


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Document Analyzer API",
        "version": "1.0.0",
        "endpoints": {
            "upload": "/upload",
            "analyze": "/analyze",
            "report": "/report/{report_id}",
            "download": "/download/{report_id}/{format}"
        }
    }


@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a document file.
    
    Args:
        file: Uploaded .docx file
        
    Returns:
        File information, upload status, and token estimation
    """
    if not file.filename.endswith('.docx'):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")
    
    # Generate unique filename
    file_id = str(uuid.uuid4())
    file_extension = Path(file.filename).suffix
    saved_filename = f"{file_id}{file_extension}"
    file_path = Path(settings.upload_dir) / saved_filename
    
    # Save file
    try:
        content = await file.read()
        
        # Check file size
        file_size_mb = len(content) / (1024 * 1024)
        if file_size_mb > settings.max_file_size_mb:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds {settings.max_file_size_mb}MB limit"
            )
        
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Calculate token estimation
        from app.document_loader import DocumentLoader
        from app.chunker import DocumentChunker
        
        loader = DocumentLoader(str(file_path))
        is_valid, error = loader.validate_file()
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=error)
        
        paragraphs = loader.extract_text()
        chunker = DocumentChunker()
        chunks = chunker.chunk_paragraphs(paragraphs)
        
        # Calculate total tokens
        total_tokens = sum(chunk['token_count'] for chunk in chunks)
        avg_chunk_tokens = total_tokens // len(chunks) if chunks else 0
        
        # Input tokens: document text + instructions per chunk
        instruction_tokens = 500  # Average instruction length
        input_tokens = total_tokens + (len(chunks) * instruction_tokens)
        
        # Output tokens: ~500 per chunk (summary + findings) + global analysis
        output_per_chunk = 500
        global_analysis_output = 1000
        output_tokens = (len(chunks) * output_per_chunk) + global_analysis_output
        
        llm_settings = get_effective_llm_settings()
        selected_provider = llm_settings["provider"]
        selected_model = llm_settings["model"]
        context_window = get_model_context_window(selected_model, settings.chunk_size)
        max_chunk_tokens = max((chunk["token_count"] for chunk in chunks), default=0)
        chunk_utilization = round((max_chunk_tokens / settings.chunk_size) * 100, 1) if settings.chunk_size else 0

        # Get estimates for all models and a focused estimate for the selected model.
        model_estimates = get_all_model_estimates(input_tokens, output_tokens)
        selected_model_estimate = None
        if selected_provider != "custom":
            selected_model_estimate = calculate_cost(input_tokens, output_tokens, selected_model)
        
        logger.info(f"File uploaded: {file.filename} -> {saved_filename}")
        
        return {
            "status": "success",
            "message": "File uploaded successfully",
            "file_id": file_id,
            "original_filename": file.filename,
            "saved_filename": saved_filename,
            "file_size_mb": round(file_size_mb, 2),
            "token_estimation": {
                "provider": selected_provider,
                "model": selected_model,
                "document_tokens": total_tokens,
                "total_chunks": len(chunks),
                "input_tokens": input_tokens,
                "estimated_output_tokens": output_tokens,
                "total_estimated_tokens": input_tokens + output_tokens,
                "avg_chunk_tokens": avg_chunk_tokens,
                "max_chunk_tokens": max_chunk_tokens,
                "instruction_tokens_assumption": instruction_tokens,
                "selected_model_estimate": selected_model_estimate,
                "context": {
                    "model_context_window_tokens": context_window,
                    "chunk_context_limit_tokens": settings.chunk_size,
                    "chunk_overlap_tokens": settings.chunk_overlap,
                    "max_chunk_tokens": max_chunk_tokens,
                    "avg_chunk_tokens": avg_chunk_tokens,
                    "max_chunk_utilization_percent": chunk_utilization,
                    "total_chunks": len(chunks),
                },
                "model_estimates": model_estimates
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.post("/analyze/{file_id}")
async def analyze_document(
    file_id: str,
    instructions: str = Form(...),
):
    """
    Analyze an uploaded document.
    
    Args:
        file_id: ID of uploaded file
        instructions: Analysis instructions
        
    Returns:
        Analysis report
    """
    # Find file
    file_path = None
    for file in Path(settings.upload_dir).glob(f"{file_id}.*"):
        file_path = file
        break
    
    if not file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        llm_config = get_effective_llm_settings()

        # Perform analysis
        analyzer = DocumentAnalyzer(str(file_path), llm_config=llm_config)
        report = analyzer.analyze(instructions)
        
        # Generate report ID
        report_id = str(uuid.uuid4())
        
        # Cache report
        analysis_cache[report_id] = report
        
        # Generate reports
        generator = ReportGenerator(report)
        json_path = generator.generate_json(f"{report_id}.json")
        docx_path = generator.generate_docx(f"{report_id}.docx")
        html_path = generator.generate_html(f"{report_id}.html")
        
        logger.info(f"Analysis complete for file {file_id}, report ID: {report_id}")
        
        return {
            "status": "success",
            "message": "Analysis completed",
            "report_id": report_id,
            "report": report.model_dump(),
            "summary": {
                "document_name": report.document_name,
                "total_chunks": report.total_chunks,
                "total_findings": report.total_findings,
                "high_severity": len(report.get_findings_by_severity('high')),
                "medium_severity": len(report.get_findings_by_severity('medium')),
                "low_severity": len(report.get_findings_by_severity('low'))
            },
            "downloads": {
                "json": f"/download/{report_id}/json",
                "docx": f"/download/{report_id}/docx",
                "html": f"/download/{report_id}/html"
            }
        }
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.get("/report/{report_id}")
async def get_report(report_id: str):
    """
    Get analysis report by ID.
    
    Args:
        report_id: Report identifier
        
    Returns:
        Analysis report data
    """
    if report_id not in analysis_cache:
        raise HTTPException(status_code=404, detail="Report not found")
    
    report = analysis_cache[report_id]
    return report.model_dump()


@app.get("/download/{report_id}/{format}")
async def download_report(report_id: str, format: str):
    """
    Download report in specified format.
    
    Args:
        report_id: Report identifier
        format: Report format (json, docx, html)
        
    Returns:
        File download response
    """
    if format not in ['json', 'docx', 'html']:
        raise HTTPException(status_code=400, detail="Invalid format. Use json, docx, or html")
    
    file_path = Path(settings.report_dir) / f"{report_id}.{format}"
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Report file not found")
    
    media_types = {
        'json': 'application/json',
        'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'html': 'text/html'
    }
    
    return FileResponse(
        path=file_path,
        media_type=media_types[format],
        filename=f"analysis_report.{format}"
    )


@app.delete("/cleanup/{file_id}")
async def cleanup_files(file_id: str):
    """
    Clean up uploaded files and reports.
    
    Args:
        file_id: File identifier
        
    Returns:
        Cleanup status
    """
    deleted = []
    
    # Delete uploaded file
    for file in Path(settings.upload_dir).glob(f"{file_id}.*"):
        file.unlink()
        deleted.append(str(file))
    
    # Delete reports
    for file in Path(settings.report_dir).glob(f"{file_id}.*"):
        file.unlink()
        deleted.append(str(file))
    
    return {
        "status": "success",
        "message": "Files cleaned up",
        "deleted_files": deleted
    }


@app.post("/settings")
async def save_user_settings(settings_data: SettingsRequest):
    """
    Save user settings to database.
    
    Args:
        settings_data: User settings
        
    Returns:
        Success status
    """
    try:
        provider = settings_data.provider.strip().lower()
        if provider not in {"openai", "anthropic", "custom"}:
            raise HTTPException(status_code=400, detail="Unsupported provider")
        if not settings_data.model.strip():
            raise HTTPException(status_code=400, detail="Model is required")
        if provider == "custom" and not (settings_data.api_base or "").strip():
            raise HTTPException(status_code=400, detail="API Base URL is required for local models")

        save_settings(
            provider=provider,
            api_key=settings_data.api_key or "",
            model=settings_data.model.strip(),
            api_base=(settings_data.api_base or "").strip() or None
        )
        return {
            "status": "success",
            "message": "Settings saved",
            "settings": {
                "provider": provider,
                "api_key": settings_data.api_key or "",
                "model": settings_data.model.strip(),
                "api_base": (settings_data.api_base or "").strip() or None,
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/settings")
async def get_user_settings():
    """
    Get user settings from database.
    
    Returns:
        User settings
    """
    try:
        return get_effective_llm_settings()
    except Exception as e:
        logger.error(f"Failed to get settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
async def get_history(limit: int = 10):
    """
    Get analysis history.
    
    Args:
        limit: Number of records to return
        
    Returns:
        Analysis history
    """
    try:
        history = get_analysis_history(limit)
        return {
            "status": "success",
            "history": history
        }
    except Exception as e:
        logger.error(f"Failed to get history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/instructions")
async def create_instruction_template(template: InstructionTemplateRequest):
    """
    Create a new instruction template.
    
    Args:
        template: Instruction template data
        
    Returns:
        Success status
    """
    try:
        save_instruction_template(
            name=template.name,
            content=template.content,
            description=template.description,
            category=template.category
        )
        return {
            "status": "success",
            "message": "Instruction template created"
        }
    except Exception as e:
        logger.error(f"Failed to create instruction template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/instructions")
async def get_instructions(category: Optional[str] = None):
    """
    Get instruction templates.
    
    Args:
        category: Optional category filter
        
    Returns:
        List of instruction templates
    """
    try:
        templates = get_instruction_templates(category)
        return {
            "status": "success",
            "templates": templates
        }
    except Exception as e:
        logger.error(f"Failed to get instruction templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/instructions/{template_id}")
async def update_instruction(template_id: int, template: InstructionTemplateUpdateRequest):
    """
    Update an instruction template.
    
    Args:
        template_id: Template ID
        template: Updated template data
        
    Returns:
        Success status
    """
    try:
        update_instruction_template(
            template_id=template_id,
            name=template.name,
            content=template.content,
            description=template.description,
            category=template.category,
            is_favorite=template.is_favorite
        )
        return {
            "status": "success",
            "message": "Instruction template updated"
        }
    except Exception as e:
        logger.error(f"Failed to update instruction template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/instructions/{template_id}/use")
async def use_instruction_template(template_id: int):
    """
    Increment use count for a template.
    
    Args:
        template_id: Template ID
        
    Returns:
        Success status
    """
    try:
        increment_template_use_count(template_id)
        return {
            "status": "success",
            "message": "Use count incremented"
        }
    except Exception as e:
        logger.error(f"Failed to increment use count: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/instructions/{template_id}")
async def delete_instruction(template_id: int):
    """
    Delete an instruction template.
    
    Args:
        template_id: Template ID
        
    Returns:
        Success status
    """
    try:
        delete_instruction_template(template_id)
        return {
            "status": "success",
            "message": "Instruction template deleted"
        }
    except Exception as e:
        logger.error(f"Failed to delete instruction template: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

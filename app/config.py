"""
Configuration module for document analyzer application.
Loads environment variables and provides application settings.
"""
import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    
    # Custom/Local Model Configuration
    custom_api_base: str = os.getenv("CUSTOM_API_BASE", "http://host.docker.internal:11434/v1")
    custom_api_key: str = os.getenv("CUSTOM_API_KEY", "ollama")
    custom_model: str = os.getenv("CUSTOM_MODEL", "llama2")
    
    # Model Configuration
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
    
    # Document Processing
    max_file_size_mb: int = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "6000"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "200"))
    
    # LLM Settings
    temperature: float = float(os.getenv("TEMPERATURE", "0.1"))
    max_output_tokens: int = int(os.getenv("MAX_OUTPUT_TOKENS", "2048"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    retry_delay: int = int(os.getenv("RETRY_DELAY", "5"))
    # Rate limiting: max requests per minute (adjust for your provider)
    max_requests_per_minute: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "8"))
    # Batching: how many chunks to send to the LLM in a single request.
    # 1 = legacy behavior (one request per chunk).
    batch_size: int = int(os.getenv("BATCH_SIZE", "10"))
    # Optional hard cap for estimated input tokens in one batch.
    # 0 = derive from the selected model context window.
    batch_max_input_tokens: int = int(os.getenv("BATCH_MAX_INPUT_TOKENS", "0"))
    # Delay (seconds) between consecutive LLM requests (batch-to-batch or chunk-to-chunk).
    request_delay: float = float(os.getenv("REQUEST_DELAY", "0.5"))
    
    # Paths
    upload_dir: str = os.getenv("UPLOAD_DIR", "uploads")
    report_dir: str = os.getenv("REPORT_DIR", "reports")
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()

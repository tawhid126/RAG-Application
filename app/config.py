"""Configuration management for the RAG application."""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Providers
    google_api_key: str
    openai_api_key: Optional[str] = None
    
    # Qdrant
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "security_manuals"
    
    # App
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"
    
    # RAG Configuration
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k_results: int = 5
    embedding_model: str = "text-embedding-004"
    chat_model: str = "gemini-1.5-flash"
    
    # Paths
    manuals_dir: str = "./data/manuals"
    logs_dir: str = "./logs"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

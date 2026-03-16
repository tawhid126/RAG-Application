"""Configuration management for the RAG application."""
from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Providers
    google_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    huggingfacehub_api_token: Optional[str] = None
    
    # Qdrant
    qdrant_url: Optional[str] = None
    qdrant_api_key: Optional[str] = None
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
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    chat_model: str = "meta-llama/Llama-3.2-1B-Instruct"
    
    # Paths
    manuals_dir: str = "./data/manuals"
    logs_dir: str = "./logs"

    # PostgreSQL (Neon) for chat history
    postgres_url: Optional[str] = None
    
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

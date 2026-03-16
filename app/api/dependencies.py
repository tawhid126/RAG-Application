"""Shared API dependencies and service instances."""
from app.config import get_settings
from app.services import (
    PDFProcessor,
    RAGService,
    LoggingService,
    WebsiteProcessor,
    YouTubeProcessor,
    DatabaseProcessor,
    get_conversation_memory,
)
from app.services.vector_store import get_vector_store

settings = get_settings()
pdf_processor = PDFProcessor()
vector_store = get_vector_store()
rag_service = RAGService()
logging_service = LoggingService()
website_processor = WebsiteProcessor()
youtube_processor = YouTubeProcessor()
database_processor = DatabaseProcessor()
conversation_memory = get_conversation_memory()

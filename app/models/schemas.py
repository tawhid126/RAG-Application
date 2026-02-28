"""Pydantic models for request/response schemas."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""
    brand: str
    manual_name: str
    page_number: int
    chunk_index: int


class DocumentChunk(BaseModel):
    """A chunk of document text with metadata."""
    text: str
    metadata: ChunkMetadata
    embedding: Optional[list[float]] = None


class Citation(BaseModel):
    """Citation information for a retrieved chunk."""
    manual_name: str
    page_number: int
    brand: str
    relevance_score: float


class QueryRequest(BaseModel):
    """User query request."""
    query: str = Field(..., min_length=1, max_length=1000, description="User's question")


class QueryResponse(BaseModel):
    """Response containing answer and citations."""
    answer: str
    citations: list[Citation]
    query: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class IngestRequest(BaseModel):
    """Request to ingest a PDF manual."""
    brand: str = Field(..., description="Brand name (e.g., 'teletek', 'duevi')")


class IngestResponse(BaseModel):
    """Response after ingesting documents."""
    status: str
    documents_processed: int
    chunks_created: int
    message: str


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    qdrant_connected: bool
    openai_configured: bool


class QueryLog(BaseModel):
    """Log entry for queries."""
    id: str
    timestamp: datetime
    query: str
    answer: str
    citations: list[Citation]
    response_time_ms: float

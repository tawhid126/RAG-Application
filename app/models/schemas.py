"""Pydantic models for request/response schemas."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    """Source type enumeration."""
    PDF = "pdf"
    WEBSITE = "website"
    YOUTUBE = "youtube"
    DATABASE = "database"
    MONGODB = "mongodb"


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""
    brand: str
    manual_name: str
    page_number: int
    chunk_index: int
    source_type: str = "pdf"
    source_url: Optional[str] = None


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
    source_type: str = "pdf"
    source_url: Optional[str] = None


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


# Conversation memory models
class ConversationMessage(BaseModel):
    """A message in a conversation."""
    role: str = Field(..., description="Message role: user, assistant, or system")
    content: str = Field(..., description="Message content")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConversationSession(BaseModel):
    """A conversation session with history."""
    session_id: str
    created_at: datetime
    last_updated: datetime
    messages: List[ConversationMessage] = Field(default_factory=list)


class ConversationQueryRequest(BaseModel):
    """Query request with conversation context."""
    query: str = Field(..., min_length=1, max_length=1000)
    session_id: Optional[str] = None
    brand_filter: Optional[str] = None


class ConversationQueryResponse(BaseModel):
    """Response with conversation context."""
    answer: str
    citations: List[Citation]
    session_id: str
    query: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# Multi-source ingestion models
class WebsiteIngestRequest(BaseModel):
    """Request to ingest websites."""
    urls: List[str] = Field(..., description="List of URLs to scrape")
    source_name: Optional[str] = Field(None, description="Optional name for this source")


class YouTubeIngestRequest(BaseModel):
    """Request to ingest YouTube videos."""
    video_urls: List[str] = Field(..., description="List of YouTube video URLs")
    languages: List[str] = Field(default=['en', 'bn'], description="Language codes for transcripts")


class DatabaseIngestRequest(BaseModel):
    """Request to ingest from SQL database."""
    connection_string: str = Field(..., description="Database connection string")
    query: Optional[str] = Field(None, description="SQL query to execute")
    table_name: Optional[str] = Field(None, description="Table name to ingest")
    source_name: Optional[str] = Field(None, description="Optional name for this source")
    limit: int = Field(default=1000, description="Maximum rows to process")


class MongoDBIngestRequest(BaseModel):
    """Request to ingest from MongoDB."""
    connection_string: str = Field(..., description="MongoDB connection string")
    database_name: str = Field(..., description="Database name")
    collection_name: str = Field(..., description="Collection name")
    query_filter: Optional[Dict[str, Any]] = Field(default=None, description="MongoDB query filter")
    limit: int = Field(default=1000, description="Maximum documents to process")


class MultiSourceIngestResponse(BaseModel):
    """Response after ingesting from any source."""
    status: str
    source_type: str
    chunks_created: int
    message: str
    citations: list[Citation]
    response_time_ms: float

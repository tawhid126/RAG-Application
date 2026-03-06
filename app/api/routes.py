"""API routes for the RAG application."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from pathlib import Path
import time
import shutil
from typing import Optional
import asyncio

from app.models.schemas import (
    QueryRequest, QueryResponse, 
    IngestRequest, IngestResponse,
    HealthResponse, ConversationQueryRequest, ConversationQueryResponse,
    WebsiteIngestRequest, YouTubeIngestRequest,
    DatabaseIngestRequest, MongoDBIngestRequest,
    MultiSourceIngestResponse
)
from app.services import (
    PDFProcessor, VectorStore, RAGService, LoggingService,
    WebsiteProcessor, YouTubeProcessor, DatabaseProcessor,
    get_conversation_memory
)
from app.config import get_settings

router = APIRouter()

# Initialize services
settings = get_settings()
pdf_processor = PDFProcessor()
vector_store = VectorStore()
rag_service = RAGService()
logging_service = LoggingService()
website_processor = WebsiteProcessor()
youtube_processor = YouTubeProcessor()
database_processor = DatabaseProcessor()
conversation_memory = get_conversation_memory()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check the health status of the application."""
    return HealthResponse(
        status="healthy",
        qdrant_connected=vector_store.is_connected(),
        openai_configured=rag_service.is_openai_configured()
    )


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, brand: Optional[str] = None):
    """
    Query the RAG system with a question.
    
    Args:
        request: QueryRequest containing the question
        brand: Optional brand filter (teletek, duevi)
        
    Returns:
        QueryResponse with answer and citations
    """
    start_time = time.time()
    
    try:
        response = rag_service.query(
            query=request.query,
            brand_filter=brand
        )
        
        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000
        
        # Log the query asynchronously
        await logging_service.log_query(response, response_time_ms)
        
        return response
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/ingest", response_model=IngestResponse)
async def ingest_manuals(request: IngestRequest):
    """
    Ingest and index all PDF manuals for a specific brand.
    
    Args:
        request: IngestRequest with brand name
        
    Returns:
        IngestResponse with processing statistics
    """
    brand = request.brand.lower()
    manuals_dir = Path(settings.manuals_dir) / brand
    
    if not manuals_dir.exists():
        raise HTTPException(
            status_code=404, 
            detail=f"Brand directory not found: {manuals_dir}"
        )
    
    # Ensure collection exists
    vector_store.create_collection()
    
    # Process all PDFs and collect chunks
    chunks = []
    documents_processed = 0
    
    try:
        for pdf_path in manuals_dir.glob("*.pdf"):
            documents_processed += 1
            for chunk in pdf_processor.process_pdf(pdf_path, brand):
                chunks.append(chunk)
        
        # Also check for uppercase PDF extension
        for pdf_path in manuals_dir.glob("*.PDF"):
            documents_processed += 1
            for chunk in pdf_processor.process_pdf(pdf_path, brand):
                chunks.append(chunk)
        
        # Add chunks to vector store
        chunks_created = vector_store.add_chunks(chunks)
        
        return IngestResponse(
            status="success",
            documents_processed=documents_processed,
            chunks_created=chunks_created,
            message=f"Successfully indexed {documents_processed} manuals with {chunks_created} chunks"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Ingestion failed: {str(e)}"
        )


@router.post("/upload")
async def upload_manual(
    file: UploadFile = File(...),
    brand: str = Form(...)
):
    """
    Upload a PDF manual for a specific brand.
    
    Args:
        file: PDF file to upload
        brand: Brand name (teletek, duevi)
        
    Returns:
        Upload status
    """
    brand = brand.lower()
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted"
        )
    
    # Create brand directory if it doesn't exist
    brand_dir = Path(settings.manuals_dir) / brand
    brand_dir.mkdir(parents=True, exist_ok=True)
    
    # Save the file
    file_path = brand_dir / file.filename
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": f"File uploaded successfully to {brand}/",
                "filename": file.filename,
                "path": str(file_path)
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@router.get("/stats")
async def get_stats():
    """Get system statistics."""
    return {
        "vector_store": vector_store.get_collection_stats(),
        "logging": logging_service.get_stats()
    }


@router.delete("/brand/{brand}")
async def delete_brand_data(brand: str):
    """
    Delete all indexed data for a specific brand.
    
    Args:
        brand: Brand name to delete
        
    Returns:
        Deletion status
    """
    try:
        vector_store.delete_by_brand(brand.lower())
        return {
            "status": "success",
            "message": f"Deleted all data for brand: {brand}"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Deletion failed: {str(e)}"
        )


@router.post("/init")
async def initialize_database():
    """
    Initialize or reinitialize the vector database.
    Creates the collection if it doesn't exist.
    """
    try:
        vector_store.create_collection(recreate=False)
        return {
            "status": "success",
            "message": "Database initialized successfully",
            "collection": settings.qdrant_collection_name
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Initialization failed: {str(e)}"
        )


# ==================== NEW ADVANCED ENDPOINTS ====================

# Streaming endpoints
@router.post("/query/stream")
async def query_stream(request: QueryRequest, brand: Optional[str] = None):
    """
    Query the RAG system with streaming response.
    
    Args:
        request: QueryRequest containing the question
        brand: Optional brand filter
        
    Returns:
        Streaming response with answer chunks and citations
    """
    try:
        return StreamingResponse(
            rag_service.query_stream(
                query=request.query,
                brand_filter=brand
            ),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stream query failed: {str(e)}")


# Conversation endpoints
@router.post("/conversation/query", response_model=ConversationQueryResponse)
async def conversation_query(request: ConversationQueryRequest):
    """
    Query with conversation memory (non-streaming).
    
    Args:
        request: ConversationQueryRequest with query and optional session_id
        
    Returns:
        ConversationQueryResponse with answer, citations, and session_id
    """
    try:
        response = rag_service.query_with_conversation(
            query=request.query,
            session_id=request.session_id,
            brand_filter=request.brand_filter
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversation query failed: {str(e)}")


@router.post("/conversation/query/stream")
async def conversation_query_stream(request: ConversationQueryRequest):
    """
    Query with conversation memory and streaming response.
    
    Args:
        request: ConversationQueryRequest with query and optional session_id
        
    Returns:
        Streaming response with session_id, answer chunks, and citations
    """
    try:
        return StreamingResponse(
            rag_service.query_with_conversation_stream(
                query=request.query,
                session_id=request.session_id,
                brand_filter=request.brand_filter
            ),
            media_type="text/event-stream"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversation stream failed: {str(e)}")


@router.get("/conversation/history/{session_id}")
async def get_conversation_history(session_id: str):
    """Get conversation history for a session."""
    history = conversation_memory.get_conversation_history(session_id)
    if not history and session_id not in conversation_memory.list_active_sessions():
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session_id,
        "messages": [msg.model_dump() for msg in history]
    }


@router.delete("/conversation/{session_id}")
async def clear_conversation(session_id: str):
    """Clear a conversation session."""
    success = conversation_memory.clear_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {"status": "success", "message": f"Cleared session: {session_id}"}


@router.get("/conversation/sessions")
async def list_sessions():
    """List all active conversation sessions."""
    sessions = conversation_memory.list_active_sessions()
    summaries = [conversation_memory.get_session_summary(sid) for sid in sessions]
    return {"sessions": summaries}


# Multi-source ingestion endpoints
@router.post("/ingest/website", response_model=MultiSourceIngestResponse)
async def ingest_website(request: WebsiteIngestRequest):
    """
    Ingest content from websites.
    
    Args:
        request: WebsiteIngestRequest with URLs and optional source name
        
    Returns:
        MultiSourceIngestResponse with status
    """
    try:
        # Ensure collection exists
        vector_store.create_collection()
        
        # Process websites
        chunks = website_processor.process_urls(
            urls=request.urls,
            source_name=request.source_name
        )
        
        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No content could be extracted from the provided URLs"
            )
        
        # Add to vector store
        chunks_created = vector_store.add_chunks(chunks)
        
        return MultiSourceIngestResponse(
            status="success",
            source_type="website",
            chunks_created=chunks_created,
            message=f"Successfully indexed {len(request.urls)} website(s) with {chunks_created} chunks"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Website ingestion failed: {str(e)}"
        )


@router.post("/ingest/youtube", response_model=MultiSourceIngestResponse)
async def ingest_youtube(request: YouTubeIngestRequest):
    """
    Ingest transcripts from YouTube videos.
    
    Args:
        request: YouTubeIngestRequest with video URLs and language preferences
        
    Returns:
        MultiSourceIngestResponse with status
    """
    try:
        # Ensure collection exists
        vector_store.create_collection()
        
        # Process YouTube videos
        chunks = youtube_processor.process_videos(
            video_urls=request.video_urls,
            languages=request.languages
        )
        
        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No transcripts could be extracted from the provided videos"
            )
        
        # Add to vector store
        chunks_created = vector_store.add_chunks(chunks)
        
        return MultiSourceIngestResponse(
            status="success",
            source_type="youtube",
            chunks_created=chunks_created,
            message=f"Successfully indexed {len(request.video_urls)} video(s) with {chunks_created} chunks"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"YouTube ingestion failed: {str(e)}"
        )


@router.post("/ingest/database", response_model=MultiSourceIngestResponse)
async def ingest_database(request: DatabaseIngestRequest):
    """
    Ingest data from SQL database.
    
    Args:
        request: DatabaseIngestRequest with connection and query details
        
    Returns:
        MultiSourceIngestResponse with status
    """
    try:
        # Ensure collection exists
        vector_store.create_collection()
        
        # Process database
        if request.query:
            chunks = database_processor.process_sql_query(
                connection_string=request.connection_string,
                query=request.query,
                source_name=request.source_name
            )
        elif request.table_name:
            chunks = database_processor.process_sql_table(
                connection_string=request.connection_string,
                table_name=request.table_name,
                limit=request.limit
            )
        else:
            raise HTTPException(
                status_code=400,
                detail="Either 'query' or 'table_name' must be provided"
            )
        
        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No data could be extracted from the database"
            )
        
        # Add to vector store
        chunks_created = vector_store.add_chunks(chunks)
        
        return MultiSourceIngestResponse(
            status="success",
            source_type="database",
            chunks_created=chunks_created,
            message=f"Successfully indexed database with {chunks_created} chunks"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Database ingestion failed: {str(e)}"
        )


@router.post("/ingest/mongodb", response_model=MultiSourceIngestResponse)
async def ingest_mongodb(request: MongoDBIngestRequest):
    """
    Ingest data from MongoDB.
    
    Args:
        request: MongoDBIngestRequest with connection and collection details
        
    Returns:
        MultiSourceIngestResponse with status
    """
    try:
        # Ensure collection exists
        vector_store.create_collection()
        
        # Process MongoDB
        chunks = database_processor.process_mongodb_collection(
            connection_string=request.connection_string,
            database_name=request.database_name,
            collection_name=request.collection_name,
            query_filter=request.query_filter,
            limit=request.limit
        )
        
        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No data could be extracted from MongoDB"
            )
        
        # Add to vector store
        chunks_created = vector_store.add_chunks(chunks)
        
        return MultiSourceIngestResponse(
            status="success",
            source_type="mongodb",
            chunks_created=chunks_created,
            message=f"Successfully indexed MongoDB collection with {chunks_created} chunks"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"MongoDB ingestion failed: {str(e)}"
        )

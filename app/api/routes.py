"""API routes for the RAG application."""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import JSONResponse
from pathlib import Path
import time
import shutil
from typing import Optional

from app.models.schemas import (
    QueryRequest, QueryResponse, 
    IngestRequest, IngestResponse,
    HealthResponse
)
from app.services import PDFProcessor, VectorStore, RAGService, LoggingService
from app.config import get_settings

router = APIRouter()

# Initialize services
settings = get_settings()
pdf_processor = PDFProcessor()
vector_store = VectorStore()
rag_service = RAGService()
logging_service = LoggingService()


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

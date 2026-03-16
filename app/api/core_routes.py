"""Core API routes for health, query, and PDF/manual operations."""
from pathlib import Path
import re
import shutil
import time
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.api.dependencies import (
    logging_service,
    pdf_processor,
    rag_service,
    settings,
    vector_store,
)
from app.models.schemas import HealthResponse, IngestRequest, IngestResponse, QueryRequest, QueryResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check the health status of the application."""
    return HealthResponse(
        status="healthy",
        qdrant_connected=vector_store.is_connected(),
        openai_configured=rag_service.is_openai_configured(),
    )


@router.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, brand: Optional[str] = None):
    """Query the RAG system with a question."""
    start_time = time.time()

    try:
        response = rag_service.query(
            query=request.query,
            brand_filter=brand,
        )

        response_time_ms = (time.time() - start_time) * 1000
        await logging_service.log_query(response, response_time_ms)

        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query failed: {str(e)}")


@router.post("/ingest", response_model=IngestResponse)
async def ingest_manuals(request: IngestRequest):
    """Ingest and index all PDF manuals for a specific brand."""
    brand = re.sub(r'[^a-zA-Z0-9_-]', '', request.brand.lower())
    if not brand:
        raise HTTPException(status_code=400, detail="Invalid brand name")
    manuals_dir = Path(settings.manuals_dir) / brand

    if not manuals_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Brand directory not found: {manuals_dir}",
        )

    vector_store.create_collection()
    documents_processed = 0
    chunks_created = 0
    batch: list = []
    _BATCH_SIZE = 200

    try:
        for pdf_path in list(manuals_dir.glob("*.pdf")) + list(manuals_dir.glob("*.PDF")):
            documents_processed += 1
            for chunk in pdf_processor.process_pdf(pdf_path, brand):
                batch.append(chunk)
                if len(batch) >= _BATCH_SIZE:
                    chunks_created += vector_store.add_chunks(batch)
                    batch.clear()

        if batch:
            chunks_created += vector_store.add_chunks(batch)

        return IngestResponse(
            status="success",
            documents_processed=documents_processed,
            chunks_created=chunks_created,
            message=f"Successfully indexed {documents_processed} manuals with {chunks_created} chunks",
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ingestion failed: {str(e)}",
        )


@router.post("/upload")
async def upload_manual(file: UploadFile = File(...), brand: str = Form(...)):
    """Upload a PDF manual for a specific brand."""
    # Sanitize brand name
    brand = re.sub(r'[^a-zA-Z0-9_-]', '', brand.lower())
    if not brand:
        raise HTTPException(status_code=400, detail="Invalid brand name")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="Only PDF files are accepted",
        )

    # Sanitize filename to prevent path traversal
    safe_filename = Path(file.filename).name
    if '..' in safe_filename or '/' in safe_filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    brand_dir = Path(settings.manuals_dir) / brand
    brand_dir.mkdir(parents=True, exist_ok=True)
    file_path = brand_dir / safe_filename

    # Verify the resolved path is within manuals_dir
    if not str(file_path.resolve()).startswith(str(Path(settings.manuals_dir).resolve())):
        raise HTTPException(status_code=400, detail="Invalid file path")

    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "message": f"File uploaded successfully to {brand}/",
                "filename": safe_filename,
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}",
        )


@router.get("/stats")
async def get_stats():
    """Get system statistics."""
    return {
        "vector_store": vector_store.get_collection_stats(),
        "logging": logging_service.get_stats(),
    }


@router.delete("/brand/{brand}")
async def delete_brand_data(brand: str):
    """Delete all indexed data for a specific brand."""
    try:
        vector_store.delete_by_brand(brand.lower())
        return {
            "status": "success",
            "message": f"Deleted all data for brand: {brand}",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Deletion failed: {str(e)}",
        )


@router.post("/init")
async def initialize_database():
    """Create the vector collection if it doesn't exist."""
    try:
        vector_store.create_collection(recreate=False)
        return {
            "status": "success",
            "message": "Database initialized successfully",
            "collection": settings.qdrant_collection_name,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Initialization failed: {str(e)}",
        )

"""Streaming API routes."""
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies import rag_service
from app.models.schemas import QueryRequest

router = APIRouter()


@router.post("/query/stream")
async def query_stream(request: QueryRequest, brand: Optional[str] = None):
    """Query the RAG system with a streaming response."""
    try:
        return StreamingResponse(
            rag_service.query_stream(
                query=request.query,
                brand_filter=brand,
            ),
            media_type="text/event-stream",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stream query failed: {str(e)}")

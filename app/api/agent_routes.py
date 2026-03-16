"""Agentic RAG API routes."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies import vector_store
from app.services.agent_service import get_agent_service
from app.models.schemas import AgentQueryRequest

router = APIRouter()


@router.post("/agent/query")
async def agent_query(request: AgentQueryRequest):
    """Process a query through the agentic RAG pipeline with streaming."""
    try:
        agent = get_agent_service()
        return StreamingResponse(
            agent.agentic_query_stream(
                query=request.query,
                session_id=request.session_id,
                source_filters=request.source_filters,
                max_iterations=request.max_iterations,
            ),
            media_type="text/event-stream",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent query failed: {str(e)}")


@router.get("/agent/sources")
async def list_sources():
    """List available sources/brands in the vector store."""
    try:
        stats = vector_store.get_collection_stats()

        results = vector_store.client.scroll(
            collection_name=vector_store.collection_name,
            limit=1000,
            with_payload=["brand", "manual_name", "source_type"],
            with_vectors=False,
        )

        brands = {}
        for point in results[0]:
            brand = point.payload.get("brand", "unknown")
            if brand not in brands:
                brands[brand] = {
                    "brand": brand,
                    "chunk_count": 0,
                    "documents": set(),
                    "source_types": set(),
                }
            brands[brand]["chunk_count"] += 1
            brands[brand]["documents"].add(point.payload.get("manual_name", ""))
            brands[brand]["source_types"].add(point.payload.get("source_type", "pdf"))

        source_list = []
        for brand_data in brands.values():
            source_list.append({
                "brand": brand_data["brand"],
                "chunk_count": brand_data["chunk_count"],
                "documents": list(brand_data["documents"]),
                "source_types": list(brand_data["source_types"]),
            })

        return {
            "sources": source_list,
            "total_chunks": stats.get("total_vectors", 0),
        }
    except Exception as e:
        return {"sources": [], "total_chunks": 0}

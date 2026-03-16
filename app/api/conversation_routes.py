"""Conversation API routes."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.dependencies import conversation_memory, rag_service
from app.models.schemas import ConversationQueryRequest, ConversationQueryResponse

router = APIRouter()


@router.post("/conversation/query", response_model=ConversationQueryResponse)
async def conversation_query(request: ConversationQueryRequest):
    """Query with conversation memory (non-streaming)."""
    try:
        response = rag_service.query_with_conversation(
            query=request.query,
            session_id=request.session_id,
            brand_filter=request.brand_filter,
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Conversation query failed: {str(e)}")


@router.post("/conversation/query/stream")
async def conversation_query_stream(request: ConversationQueryRequest):
    """Query with conversation memory and streaming response."""
    try:
        return StreamingResponse(
            rag_service.query_with_conversation_stream(
                query=request.query,
                session_id=request.session_id,
                brand_filter=request.brand_filter,
            ),
            media_type="text/event-stream",
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
        "messages": [msg.model_dump() for msg in history],
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

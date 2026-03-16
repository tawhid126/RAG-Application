"""Chat history API routes (backed by Neon PostgreSQL)."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.postgres_history import (
    get_all_conversations,
    save_conversation,
    get_conversation,
    delete_conversation,
)

router = APIRouter()


class SaveConversationRequest(BaseModel):
    id: str
    title: str
    html: str


@router.get("/history")
def list_conversations():
    try:
        return {"conversations": get_all_conversations()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/history")
def upsert_conversation(req: SaveConversationRequest):
    try:
        save_conversation(req.id, req.title, req.html)
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{conv_id}")
def get_conv(conv_id: str):
    try:
        conv = get_conversation(conv_id)
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return conv
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/history/{conv_id}")
def delete_conv(conv_id: str):
    try:
        deleted = delete_conversation(conv_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"status": "ok"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

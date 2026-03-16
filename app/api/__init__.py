"""API package."""
from fastapi import APIRouter

from app.api.agent_routes import router as agent_router
from app.api.conversation_routes import router as conversation_router
from app.api.core_routes import router as core_router
from app.api.history_routes import router as history_router
from app.api.ingestion_routes import router as ingestion_router
from app.api.streaming_routes import router as streaming_router

router = APIRouter()
router.include_router(core_router)
router.include_router(streaming_router)
router.include_router(conversation_router)
router.include_router(ingestion_router)
router.include_router(agent_router)
router.include_router(history_router)

__all__ = ["router"]

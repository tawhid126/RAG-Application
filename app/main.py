"""FastAPI main application."""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import logging

from app.api import router
from app.config import get_settings

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Universal Knowledge Assistant",
    description="Multi-Source RAG system with PDF, Website, YouTube, and Database support - featuring streaming responses and conversation memory",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api", tags=["API"])

# Mount static files for the web interface
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/", StaticFiles(directory=str(static_path), html=True), name="static")


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("=" * 60)
    logger.info("Starting Universal Knowledge Assistant (Multi-Source RAG)")
    logger.info("=" * 60)
    logger.info(f"Version: 2.0.0")
    logger.info(f"Qdrant: {settings.qdrant_host}:{settings.qdrant_port}")
    logger.info(f"Collection: {settings.qdrant_collection_name}")
    logger.info(f"Data directory: {settings.manuals_dir}")
    logger.info(f"Features: PDF | Website | YouTube | Database")
    logger.info(f"Streaming: Enabled | Conversation Memory: Enabled")
    logger.info("=" * 60)


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Universal Knowledge Assistant...")
    logger.info("Cleaning up conversation sessions...")
    from app.services import get_conversation_memory
    memory = get_conversation_memory()
    cleaned = memory.cleanup_old_sessions()
    logger.info(f"Cleaned {cleaned} old sessions")
    logger.info("Shutdown complete")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=True
    )

"""Logging service for query tracking."""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional
import structlog
import aiofiles

from app.config import get_settings
from app.models.schemas import QueryResponse, QueryLog


# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
)


class LoggingService:
    """Service for logging queries and responses."""
    
    def __init__(self):
        self.settings = get_settings()
        self.logs_dir = Path(self.settings.logs_dir)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.logger = structlog.get_logger("rag_queries")
    
    def _get_log_file(self) -> Path:
        """Get the log file path for today."""
        today = datetime.utcnow().strftime("%Y-%m-%d")
        return self.logs_dir / f"queries_{today}.jsonl"
    
    async def log_query(
        self,
        response: QueryResponse,
        response_time_ms: float
    ) -> str:
        """
        Log a query and its response.
        
        Args:
            response: The QueryResponse object
            response_time_ms: Response time in milliseconds
            
        Returns:
            Log entry ID
        """
        log_id = str(uuid.uuid4())
        
        log_entry = QueryLog(
            id=log_id,
            timestamp=response.timestamp,
            query=response.query,
            answer=response.answer,
            citations=response.citations,
            response_time_ms=response_time_ms
        )
        
        # Write to JSONL file
        log_file = self._get_log_file()
        async with aiofiles.open(log_file, "a") as f:
            await f.write(log_entry.model_dump_json() + "\n")
        
        # Also log with structlog for monitoring
        self.logger.info(
            "query_processed",
            log_id=log_id,
            query=response.query[:100],  # Truncate for log readability
            citations_count=len(response.citations),
            response_time_ms=response_time_ms
        )
        
        return log_id
    
    async def get_recent_logs(
        self,
        limit: int = 100,
        days_back: int = 7
    ) -> list[QueryLog]:
        """
        Get recent query logs.
        
        Args:
            limit: Maximum number of logs to return
            days_back: Number of days to look back
            
        Returns:
            List of QueryLog objects
        """
        logs = []
        
        # Get log files for the date range
        for i in range(days_back):
            date = datetime.utcnow()
            date = date.replace(day=date.day - i)
            log_file = self.logs_dir / f"queries_{date.strftime('%Y-%m-%d')}.jsonl"
            
            if log_file.exists():
                async with aiofiles.open(log_file, "r") as f:
                    async for line in f:
                        if line.strip():
                            log_entry = QueryLog.model_validate_json(line)
                            logs.append(log_entry)
                            
                            if len(logs) >= limit:
                                break
            
            if len(logs) >= limit:
                break
        
        # Sort by timestamp descending
        logs.sort(key=lambda x: x.timestamp, reverse=True)
        return logs[:limit]
    
    def get_stats(self) -> dict:
        """Get logging statistics."""
        stats = {
            "logs_directory": str(self.logs_dir),
            "log_files": []
        }
        
        for log_file in sorted(self.logs_dir.glob("queries_*.jsonl"), reverse=True)[:7]:
            line_count = 0
            with open(log_file, "r") as f:
                line_count = sum(1 for _ in f)
            
            stats["log_files"].append({
                "date": log_file.stem.replace("queries_", ""),
                "queries_count": line_count
            })
        
        return stats

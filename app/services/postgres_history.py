"""PostgreSQL (Neon) based chat history service.

Uses a fresh connection per request — correct approach for Neon serverless
where idle connections are dropped by the server.
"""
import logging
from typing import List, Optional, Dict, Any

import psycopg2
import psycopg2.extras

from app.config import get_settings

logger = logging.getLogger(__name__)


def _connect():
    """Open a fresh connection to Neon Postgres."""
    url = get_settings().postgres_url
    if not url:
        raise RuntimeError("POSTGRES_URL is not set in environment variables")
    return psycopg2.connect(url)


def init_db() -> None:
    """Create the chat_history table if it doesn't exist."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS chat_history (
                    id          VARCHAR PRIMARY KEY,
                    title       VARCHAR(200) NOT NULL,
                    html        TEXT NOT NULL,
                    created_at  TIMESTAMPTZ DEFAULT NOW(),
                    updated_at  TIMESTAMPTZ DEFAULT NOW()
                )
            """)
        conn.commit()
        logger.info("chat_history table ready")
    finally:
        conn.close()


def get_all_conversations() -> List[Dict[str, Any]]:
    """Return all conversations ordered by most recently updated (max 30)."""
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, title, updated_at FROM chat_history ORDER BY updated_at DESC LIMIT 30"
            )
            rows = cur.fetchall()
        return [
            {
                "id": row["id"],
                "title": row["title"],
                "timestamp": row["updated_at"].timestamp() * 1000,
            }
            for row in rows
        ]
    finally:
        conn.close()


def save_conversation(id: str, title: str, html: str) -> None:
    """Insert or update a conversation."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_history (id, title, html, updated_at)
                VALUES (%s, %s, %s, NOW())
                ON CONFLICT (id) DO UPDATE
                    SET title = EXCLUDED.title,
                        html  = EXCLUDED.html,
                        updated_at = NOW()
                """,
                (id, title, html),
            )
        conn.commit()
    finally:
        conn.close()


def get_conversation(id: str) -> Optional[Dict[str, Any]]:
    """Return a single conversation including HTML."""
    conn = _connect()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, title, html, updated_at FROM chat_history WHERE id = %s",
                (id,),
            )
            row = cur.fetchone()
        if row:
            return {
                "id": row["id"],
                "title": row["title"],
                "html": row["html"],
                "timestamp": row["updated_at"].timestamp() * 1000,
            }
        return None
    finally:
        conn.close()


def delete_conversation(id: str) -> bool:
    """Delete a conversation. Returns True if a row was deleted."""
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM chat_history WHERE id = %s", (id,))
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    finally:
        conn.close()

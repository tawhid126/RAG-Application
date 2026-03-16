"""Conversation memory service for maintaining chat history."""
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
import uuid
import threading

from app.models.schemas import ConversationMessage, ConversationSession
from app.config import get_settings

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Manage conversation history and context."""

    def __init__(self):
        self.settings = get_settings()
        self.sessions: Dict[str, ConversationSession] = {}
        self.max_history = 10  # Maximum messages to keep in context
        self._cleanup_interval = timedelta(hours=24)  # Cleanup old sessions
        self._lock = threading.Lock()
    
    def create_session(self, session_id: Optional[str] = None) -> str:
        """
        Create a new conversation session.
        
        Args:
            session_id: Optional session ID, generates one if not provided
            
        Returns:
            Session ID
        """
        if session_id is None:
            session_id = str(uuid.uuid4())

        with self._lock:
            self.sessions[session_id] = ConversationSession(
                session_id=session_id,
                created_at=datetime.utcnow(),
                last_updated=datetime.utcnow(),
                messages=[]
            )
        
        logger.info(f"Created new conversation session: {session_id}")
        return session_id
    
    def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """
        Get a conversation session.
        
        Args:
            session_id: Session ID
            
        Returns:
            ConversationSession or None if not found
        """
        return self.sessions.get(session_id)
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """
        Add a message to a conversation session.
        
        Args:
            session_id: Session ID
            role: Message role (user/assistant/system)
            content: Message content
            metadata: Optional metadata
        """
        with self._lock:
            if session_id not in self.sessions:
                self.create_session(session_id)

            message = ConversationMessage(
                role=role,
                content=content,
                timestamp=datetime.utcnow(),
                metadata=metadata or {}
            )

            self.sessions[session_id].messages.append(message)
            self.sessions[session_id].last_updated = datetime.utcnow()

            # Keep only the last N messages to prevent memory bloat
            if len(self.sessions[session_id].messages) > self.max_history * 2:
                # Keep system message if exists, then last N pairs
                messages = self.sessions[session_id].messages
                system_messages = [m for m in messages if m.role == "system"]
                other_messages = [m for m in messages if m.role != "system"]
                self.sessions[session_id].messages = system_messages + other_messages[-(self.max_history * 2):]
    
    def get_conversation_history(
        self,
        session_id: str,
        max_messages: Optional[int] = None
    ) -> List[ConversationMessage]:
        """
        Get conversation history for a session.
        
        Args:
            session_id: Session ID
            max_messages: Maximum number of recent messages to return
            
        Returns:
            List of ConversationMessage objects
        """
        if session_id not in self.sessions:
            return []
        
        messages = self.sessions[session_id].messages
        
        if max_messages:
            return messages[-max_messages:]
        
        return messages
    
    def get_context_for_llm(
        self,
        session_id: str,
        max_messages: Optional[int] = None
    ) -> List[Dict[str, str]]:
        """
        Get conversation history formatted for LLM API.
        
        Args:
            session_id: Session ID
            max_messages: Maximum number of recent messages to return
            
        Returns:
            List of message dictionaries in OpenAI format
        """
        messages = self.get_conversation_history(session_id, max_messages)
        
        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
    
    def clear_session(self, session_id: str) -> bool:
        """
        Clear a conversation session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if session was cleared, False if not found
        """
        with self._lock:
            if session_id in self.sessions:
                del self.sessions[session_id]
                logger.info(f"Cleared conversation session: {session_id}")
                return True
            return False
    
    def cleanup_old_sessions(self) -> int:
        """
        Remove sessions that haven't been updated recently.
        
        Returns:
            Number of sessions removed
        """
        with self._lock:
            now = datetime.utcnow()
            old_sessions = [
                sid for sid, session in self.sessions.items()
                if now - session.last_updated > self._cleanup_interval
            ]

            for sid in old_sessions:
                del self.sessions[sid]
        
        if old_sessions:
            logger.info(f"Cleaned up {len(old_sessions)} old conversation sessions")
        
        return len(old_sessions)
    
    def get_session_summary(self, session_id: str) -> Optional[Dict]:
        """
        Get a summary of a conversation session.
        
        Args:
            session_id: Session ID
            
        Returns:
            Dictionary with session summary
        """
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]

        user_msgs = 0
        assistant_msgs = 0
        for m in session.messages:
            if m.role == "user":
                user_msgs += 1
            elif m.role == "assistant":
                assistant_msgs += 1

        return {
            "session_id": session_id,
            "created_at": session.created_at.isoformat(),
            "last_updated": session.last_updated.isoformat(),
            "message_count": len(session.messages),
            "user_messages": user_msgs,
            "assistant_messages": assistant_msgs,
        }
    
    def list_active_sessions(self) -> List[str]:
        """
        Get list of active session IDs.
        
        Returns:
            List of session IDs
        """
        return list(self.sessions.keys())


# Global instance
_conversation_memory = None


def get_conversation_memory() -> ConversationMemory:
    """Get the global conversation memory instance."""
    global _conversation_memory
    if _conversation_memory is None:
        _conversation_memory = ConversationMemory()
    return _conversation_memory

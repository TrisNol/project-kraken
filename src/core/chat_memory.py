from datetime import datetime
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field
from collections import defaultdict
from threading import Lock


class ChatHistoryMessage(BaseModel):
    """Represents a single message in the chat history"""
    role: str = Field(..., description="Role of the message sender (user or assistant)")
    content: str = Field(..., description="Content of the message")
    timestamp: datetime = Field(default_factory=datetime.now, description="When the message was created")
    sources: Optional[List[Dict[str, Any]]] = Field(default=None, description="Source documents used for this message")
    

class ChatMemory:
    """In-memory storage for chat history organized by session ID"""
    
    def __init__(self, max_messages_per_session: int = 50):
        self._memory: Dict[str, List[ChatHistoryMessage]] = defaultdict(list)
        self._lock = Lock()
        self.max_messages_per_session = max_messages_per_session
    
    def add_message(self, session_id: str, role: str, content: str, sources: Optional[List[Dict[str, Any]]] = None) -> None:
        """
        Add a message to the chat history for a given session.
        
        Args:
            session_id: The session identifier
            role: The role of the sender ('user' or 'assistant')
            content: The message content
            sources: Optional list of source documents used for this message
        """
        with self._lock:
            message = ChatHistoryMessage(role=role, content=content, sources=sources)
            self._memory[session_id].append(message)
            
            # Keep only the last N messages to prevent unlimited growth
            if len(self._memory[session_id]) > self.max_messages_per_session:
                self._memory[session_id] = self._memory[session_id][-self.max_messages_per_session:]
    
    def get_history(self, session_id: str, limit: Optional[int] = None) -> List[ChatHistoryMessage]:
        """
        Retrieve chat history for a given session.
        
        Args:
            session_id: The session identifier
            limit: Optional limit on number of messages to return (most recent)
            
        Returns:
            List of chat history messages
        """
        with self._lock:
            messages = self._memory.get(session_id, [])
            if limit:
                return messages[-limit:]
            return messages.copy()
    
    def get_context_for_rag(self, session_id: str, max_history: int = 5) -> str:
        """
        Get formatted conversation history for RAG context.
        Returns the last N exchanges to provide conversational context.
        
        Args:
            session_id: The session identifier
            max_history: Maximum number of previous messages to include
            
        Returns:
            Formatted string with conversation history
        """
        with self._lock:
            messages = self._memory.get(session_id, [])
            if not messages:
                return ""
            
            # Get the last N messages
            recent_messages = messages[-max_history:] if len(messages) > max_history else messages
            
            # Format as conversation history
            context_parts = ["Previous conversation:"]
            for msg in recent_messages:
                prefix = "User" if msg.role == "user" else "Assistant"
                context_parts.append(f"{prefix}: {msg.content}")
            
            return "\n".join(context_parts)
    
    def clear_session(self, session_id: str) -> None:
        """
        Clear chat history for a specific session.
        
        Args:
            session_id: The session identifier
        """
        with self._lock:
            if session_id in self._memory:
                del self._memory[session_id]

    def clear_all(self) -> None:
        """Clear all chat histories"""
        with self._lock:
            self._memory.clear()
    
    def get_session_count(self) -> int:
        """Get the total number of active sessions"""
        with self._lock:
            return len(self._memory)

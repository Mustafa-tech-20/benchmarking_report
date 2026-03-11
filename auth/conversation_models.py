"""
Conversation History Data Models
"""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel


class ConversationMessage(BaseModel):
    """Individual message in a conversation"""
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime
    report_url: Optional[str] = None
    cars_compared: Optional[str] = None
    time_taken: Optional[str] = None


class Conversation(BaseModel):
    """Conversation model"""
    conversation_id: str
    user_email: str
    title: str  # Auto-generated from first message
    messages: List[ConversationMessage]
    created_at: datetime
    updated_at: datetime
    session_id: Optional[str] = None
    user_id: Optional[str] = None


class ConversationListItem(BaseModel):
    """Conversation summary for list view"""
    conversation_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int

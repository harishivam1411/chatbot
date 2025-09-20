
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class ChatRequest(BaseModel):
    query: str
    user_id: str
    session_id: str


class ChatResponse(BaseModel):
    reply: str
    category: str


class ChatMessage(BaseModel):
    session_id: str
    user_id: str
    message: str
    sender: str
    category: str
    timestamp: datetime

    class Config:
        from_attributes = True

class MessageResponse(BaseModel):
    id: int
    message: str
    sender: str
    timestamp: str

class ConversationResponse(BaseModel):
    session_id: str
    messages: List[MessageResponse]
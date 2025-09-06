from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    reply: str
    category: str
    log_id: int


class LogItem(BaseModel):
    id: int
    conversation_id: Optional[str]
    user_id: Optional[str]
    user_message: str
    bot_response: str
    category: str
    created_at: datetime


    class Config:
        from_attributes = True


class AnalysisSummary(BaseModel):
    counts: dict
    most_used: str | None
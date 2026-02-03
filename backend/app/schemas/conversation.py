from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import List, Optional


class ConversationOut(BaseModel):
    id: int
    title: str | None
    started_at: datetime
    ended_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class CitationOut(BaseModel):
    title: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    snippet: Optional[str] = None


class ChatMessageOut(BaseModel):
    id: int
    role: str
    content: str
    created_at: datetime
    # 🔴 SAFETY METADATA
    risk_level: Optional[str] = None
    emergency_detected: Optional[bool] = None
    confidence_score: Optional[float] = None
    model_name: Optional[str] = None

    citations: Optional[List[CitationOut]] = None

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailOut(BaseModel):
    conversation: ConversationOut
    messages: List[ChatMessageOut]

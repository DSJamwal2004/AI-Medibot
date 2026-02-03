from pydantic import BaseModel
from typing import Optional, List

class Citation(BaseModel):
    title: Optional[str]
    source: Optional[str]
    source_file: Optional[str]
    page_number: Optional[int]
    medical_domain: Optional[str]
    authority_level: Optional[int]

class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[int] = None


class ChatResponse(BaseModel):
    conversation_id: int
    reply: str
    citations: List[Citation] = []
    chat_message_id: int

    # 🔐 Safety metadata (NEW)
    risk_level: Optional[str] = None
    emergency_detected: Optional[bool] = None
    confidence_score: Optional[float] = None
    suppression_reason: Optional[str] = None
    model_mode: Optional[str] = None  # "online" | "offline"





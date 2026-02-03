from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime


class ExplainResponse(BaseModel):
    chat_message_id: int
    risk_level: str
    emergency_detected: bool
    risk_reason: str
    risk_trigger: Optional[str]

    primary_domain: Optional[str]
    all_domains: Optional[List[Dict[str, Any]]]

    confidence_score: float
    model_name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


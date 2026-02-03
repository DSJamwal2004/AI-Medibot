from sqlalchemy import Column, Integer, ForeignKey, String, DateTime, Boolean, Text
from sqlalchemy.sql import func
from app.db.base import Base


class DoctorEscalation(Base):
    __tablename__ = "doctor_escalations"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    conversation_id = Column(Integer, ForeignKey("conversations.id"), nullable=False)

    reason = Column(String, nullable=False)
    notes = Column(Text, nullable=True)

    resolved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

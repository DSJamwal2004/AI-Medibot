from sqlalchemy import (
    Column,
    Integer,
    ForeignKey,
    Boolean,
    DateTime,
    Text,
    String,
    JSON,
    Float,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.db.base import Base


class MedicalInteraction(Base):
    """
    Stores explainable, auditable medical intelligence
    derived from a USER chat message.
    """

    __tablename__ = "medical_interactions"

    id = Column(Integer, primary_key=True, index=True)

    # 🔗 Traceability
    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # ✅ FIX 1: correct table name (chat_messages)
    chat_message_id = Column(
        Integer,
        ForeignKey("chat_messages.id", ondelete="CASCADE"),
        nullable=True,   # nullable to support legacy rows
        unique=True,
        index=True,
    )

    # 🛑 Risk assessment (deterministic)
    risk_level = Column(String, nullable=False)
    risk_reason = Column(Text, nullable=False)
    risk_trigger = Column(String, nullable=True)

    emergency_detected = Column(Boolean, default=False, nullable=False)

    # 🧠 Domain inference
    primary_domain = Column(String, nullable=True)
    all_domains = Column(JSON, nullable=True)

    # 🧭 Conversation intelligence (NEW)
    conversation_phase = Column(
        String(32),
        nullable=True,
        index=True,
    )

    slots_collected = Column(
        JSON,
        nullable=True,
        doc="Heuristically detected medical evidence slots (duration, severity, etc.)",
    )

    # 📊 Optional scoring / UX
    confidence_score = Column(Float, nullable=False, default=0.5)
    reasoning_summary = Column(Text, nullable=True)

    disclaimer_shown = Column(Boolean, default=True, nullable=False)

    # 🧾 Metadata
    model_name = Column(String, nullable=False, default="deterministic-rag")

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # ✅ FIX 2: explicit relationship binding
    chat_message = relationship(
        "ChatMessage",
        foreign_keys=[chat_message_id],
        back_populates="medical_interaction",
        lazy="joined",
    )




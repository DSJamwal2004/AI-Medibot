from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.models.conversation import Conversation
from app.models.chat_message import ChatMessage
from app.models.medical_interaction import MedicalInteraction
from app.schemas.conversation import (
    ConversationOut,
    ConversationDetailOut,
    ChatMessageOut,
)

router = APIRouter(prefix="/conversations", tags=["Conversations"])


# 1️⃣ List conversations (most recent first)
@router.get("", response_model=list[ConversationOut])
def list_conversations(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    conversations = (
        db.query(Conversation)
        .filter(Conversation.user_id == current_user.id)
        .order_by(Conversation.started_at.desc())
        .all()
    )
    return conversations


# 2️⃣ Get a conversation + messages
@router.get("/{conversation_id}", response_model=ConversationDetailOut)
def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == current_user.id,
        )
        .first()
    )

    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation.id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    message_ids = [m.id for m in messages]

    interactions = (
        db.query(MedicalInteraction)
        .filter(MedicalInteraction.chat_message_id.in_(message_ids))
        .all()
    )

    interaction_map = {i.chat_message_id: i for i in interactions}

    hydrated_messages = []

    for m in messages:
        interaction = interaction_map.get(m.id)

        hydrated_messages.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at,

            # 🔴 SAFETY
            "risk_level": interaction.risk_level if interaction else None,
            "emergency_detected": interaction.emergency_detected if interaction else None,
            "confidence_score": interaction.confidence_score if interaction else None,
            "model_name": interaction.model_name if interaction else None,
        })

    return {
        "conversation": conversation,
        "messages": hydrated_messages,
    }

# 3 Medical-Audit
@router.get("/{conversation_id}/medical-audit")
def get_medical_audit(
    conversation_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    logs = (
        db.query(MedicalInteraction)
        .filter(
            MedicalInteraction.conversation_id == conversation_id,
            MedicalInteraction.user_id == current_user.id,
        )
        .order_by(MedicalInteraction.created_at.asc())
        .all()
    )
    return logs
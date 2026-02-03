from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import Dict, Any
from sqlalchemy import or_, and_

from app.models.chat_message import ChatMessage
from app.models.medical_interaction import MedicalInteraction


def get_explanation_for_message(
    db: Session,
    *,
    chat_message_id: int,
    user_id: int,
) -> Dict[str, Any]:
    """
    Returns deterministic explanation.

    Rules:
    - MedicalInteraction is stored for USER messages only.
    - If given an ASSISTANT message id, we resolve the nearest previous USER message
      within the same conversation (with created_at + id tie-break).
    """

    # 1) Load the message (user or assistant)
    message = (
        db.query(ChatMessage)
        .filter(
            ChatMessage.id == chat_message_id,
            ChatMessage.user_id == user_id,
        )
        .first()
    )

    if not message:
        raise HTTPException(status_code=404, detail="Chat message not found")

    # 2) Resolve the USER message id that owns the MedicalInteraction
    target_user_message = message

    if message.role == "assistant":
        prev_user_msg = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.conversation_id == message.conversation_id,
                ChatMessage.user_id == user_id,
                ChatMessage.role == "user",
                or_(
                    ChatMessage.created_at < message.created_at,
                    and_(
                        ChatMessage.created_at == message.created_at,
                        ChatMessage.id < message.id,
                    ),
                ),
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .first()
        )

        if not prev_user_msg:
            raise HTTPException(
                status_code=404,
                detail="No previous user message found for this assistant message",
            )

        target_user_message = prev_user_msg

    # 3) Load MedicalInteraction for that USER message
    interaction = (
        db.query(MedicalInteraction)
        .filter(
            MedicalInteraction.chat_message_id == target_user_message.id,
            MedicalInteraction.user_id == user_id,
        )
        .first()
    )

    if not interaction:
        raise HTTPException(
            status_code=404,
            detail="No medical explanation found for this message",
        )

    # 4) RAG meta comes from ASSISTANT message meta (if the current is user, try next assistant)
    rag_meta = {}
    if message.role == "assistant":
        rag_meta = (message.meta or {}).get("rag", {})
    else:
        # optional: if explain called on USER msg, try to find the next assistant for rag meta
        next_assistant = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.conversation_id == message.conversation_id,
                ChatMessage.user_id == user_id,
                ChatMessage.role == "assistant",
                or_(
                    ChatMessage.created_at > message.created_at,
                    and_(
                        ChatMessage.created_at == message.created_at,
                        ChatMessage.id > message.id,
                    ),
                ),
            )
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
            .first()
        )
        if next_assistant:
            rag_meta = (next_assistant.meta or {}).get("rag", {})

    explanation = {
        "message_id": chat_message_id,
        "resolved_user_message_id": target_user_message.id,
        "risk_assessment": {
            "level": interaction.risk_level,
            "reason": interaction.risk_reason,
            "trigger": interaction.risk_trigger,
            "emergency_detected": interaction.emergency_detected,
        },
        "medical_domain": interaction.primary_domain,
        "confidence_score": interaction.confidence_score,
        "rag": {
            "citations_returned": rag_meta.get("citations_returned", False),
            "suppression_reason": rag_meta.get("suppression_reason"),
            "retrieved_sources": rag_meta.get("retrieved_chunks", []),
            "rag_confidence": rag_meta.get("rag_confidence"),
        },
        "why_this_answer": _build_reasoning_summary(
            interaction=interaction,
            rag_meta=rag_meta,
        ),
    }

    return explanation

def _build_reasoning_summary(
    *,
    interaction: MedicalInteraction,
    rag_meta: Dict[str, Any],
) -> str:
    """
    Deterministic explanation summary.
    This is NOT an LLM output.
    """

    reasons = []

    if interaction.risk_level:
        reasons.append(
            f"risk level was assessed as {interaction.risk_level.lower()}"
        )

    if interaction.primary_domain:
        reasons.append(
            f"the medical domain '{interaction.primary_domain}' was inferred"
        )

    suppression_reason = rag_meta.get("suppression_reason")
    if suppression_reason:
        reasons.append(
            f"citations were intentionally suppressed due to '{suppression_reason}'"
        )
    else:
        retrieved = rag_meta.get("retrieved_chunks", [])
        if retrieved:
            reasons.append(
                f"{len(retrieved)} trusted medical sources were retrieved"
            )

    if interaction.confidence_score is not None:
        reasons.append(
            f"confidence score was {interaction.confidence_score:.2f}"
        )

    return "The response was generated because " + ", and ".join(reasons) + "."



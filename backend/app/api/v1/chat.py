from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from sqlalchemy import or_, and_
import traceback

from app.db.session import get_db
from app.core.dependencies import get_current_user

from app.schemas.chat import ChatRequest, ChatResponse

from app.services.chat_service import (
    get_or_create_conversation,
    save_message,
    get_conversation_history,
    analyze_user_message,
    is_informational_message,
    process_chat_message
)

from app.services.medical_interaction_service import save_medical_interaction
from app.services.escalation_rules import should_escalate
from app.models.doctor_escalation import DoctorEscalation

from app.schemas.explain import ExplainResponse
from app.services.explain_service import get_explanation_for_message

from app.services.rag_service import retrieve_context
from app.services.ai_service import generate_ai_reply


# --------------------------------------------------
# Symptom ambiguity detection (UX safety)
# --------------------------------------------------

KNOWN_CONDITIONS = {
    "diabetes",
    "hypertension",
    "migraine",
    "asthma",
    "cancer",
    "flu",
    "covid",
    "pneumonia",
    "stroke",
    "heart attack",
}


def is_greeting(text: str) -> bool:
    t = (text or "").strip().lower()
    return t in {"hi", "hello", "hey", "hii", "hiii", "yo"} or t.startswith(("hi ", "hello ", "hey "))


def is_thanks(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(x in t for x in ["thanks", "thank you", "thx"])


def is_goodbye(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(x in t for x in ["bye", "goodbye", "see you", "take care"])


def is_capability_query(text: str) -> bool:
    t = (text or "").strip().lower()
    return any(x in t for x in ["what can you do", "help", "how do you work", "what do you do"])


def is_vague_followup(text: str) -> bool:
    """
    Detect vague follow-up messages that depend on previous context.
    Examples:
    - "what should I do?"
    - "what next?"
    - "help"
    - "tell me more"
    """
    t = (text or "").strip().lower()

    patterns = [
        "what do i do",
        "what should i do",
        "what do you suggest",
        "what next",
        "what now",
        "next",
        "help",
        "tell me more",
        "more",
        "why",
        "how",
        "what can i do",
    ]

    # super short vague prompts
    if len(t.split()) <= 4 and t in {"why", "how", "what", "help", "next"}:
        return True

    return any(p in t for p in patterns)


def has_explicit_condition(text: str) -> bool:
    text_lower = (text or "").lower()
    return any(cond in text_lower for cond in KNOWN_CONDITIONS)


def is_medication_query(text: str) -> bool:
    """
    Medication queries should NOT be treated as ambiguous symptoms.
    They often need citations for safe guidance (interactions, dosage, misuse).
    """
    t = (text or "").lower()

    markers = [
        "medicine", "medication", "drug", "tablet", "pill",
        "dose", "dosage",
        "side effect", "side effects",
        "interaction", "interactions",
        "can i take", "can we take",
        "together", "with",
        "overdose", "missed dose",
        "antibiotic", "antibiotics",
        "warfarin", "ibuprofen", "paracetamol", "acetaminophen",
        "metformin", "insulin",
    ]

    return any(m in t for m in markers)


def get_citation_suppression_reason(message: str, analysis: dict, chunks: list) -> Optional[str]:
    """
    Returns a suppression reason string if citations should be hidden.
    If None => citations allowed.
    """

    if analysis.get("emergency_detected"):
        return "emergency_override"

    if not chunks:
        return "no_high_confidence_sources"

    # Medication queries should allow citations
    if is_medication_query(message):
        return None

    # Informational questions should allow citations
    if is_informational_message(message):
        return None

    # Otherwise treat vague symptom statements as ambiguous (suppress citations)
    if not has_explicit_condition(message):
        return "ambiguous_symptoms"

    return None


def _get_last_domain_from_db(db: Session, conversation_id: int) -> Optional[str]:
    """
    Helps keep the same medical domain for vague follow-ups.
    Looks at last stored MedicalInteraction for this conversation.
    """
    try:
        from app.models.medical_interaction import MedicalInteraction
        from app.models.chat_message import ChatMessage

        last = (
            db.query(MedicalInteraction)
            .join(ChatMessage, ChatMessage.id == MedicalInteraction.chat_message_id)
            .filter(ChatMessage.conversation_id == conversation_id)
            .order_by(MedicalInteraction.created_at.desc())
            .first()
        )
        if last and last.primary_domain and last.primary_domain != "general":
            return last.primary_domain
    except Exception:
        return None

    return None


router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
def chat(
    payload: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        result = process_chat_message(
            db=db,
            user_id=current_user.id,
            conversation_id=payload.conversation_id,
            message=payload.message,
            is_greeting=is_greeting,
            is_thanks=is_thanks,
            is_goodbye=is_goodbye,
            is_capability_query=is_capability_query,
            is_vague_followup=is_vague_followup,
            has_explicit_condition=has_explicit_condition,
            is_medication_query=is_medication_query,
            get_citation_suppression_reason=get_citation_suppression_reason,
            get_last_domain_from_db=_get_last_domain_from_db,
        )

        analysis = result["analysis"]

        return ChatResponse(
            conversation_id=result["conversation_id"],
            reply=result["reply"],
            citations=result["citations"],
            chat_message_id=result["assistant_message_id"],
            risk_level=analysis["risk_level"],
            emergency_detected=analysis["emergency_detected"],
            confidence_score=float(result["confidence_score"]),
            suppression_reason=result["suppression_reason"],
            model_mode=result["model_mode"],
        )

    except Exception as e:
        db.rollback()
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/{chat_message_id}/escalate")
def escalate_to_doctor(
    chat_message_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.models.chat_message import ChatMessage
    from app.models.doctor_escalation import DoctorEscalation

    msg = db.query(ChatMessage).filter(ChatMessage.id == chat_message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Chat message not found")

    if msg.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    escalation = DoctorEscalation(
        user_id=current_user.id,
        conversation_id=msg.conversation_id,
        reason="manual_user_request",
        notes="User requested doctor escalation from chat UI",
    )
    db.add(escalation)
    db.commit()

    return {"status": "escalated"}


@router.get("/chat/{chat_message_id}/explain", response_model=ExplainResponse)
def explain_chat_decision(
    chat_message_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """
    Returns deterministic medical reasoning for a given chat message.

    IMPORTANT:
    - Medical explanations are stored for USER messages.
    - If the given chat_message_id belongs to an ASSISTANT message,
      we automatically resolve the explanation for the nearest previous USER message.
    """
    from app.models.chat_message import ChatMessage
    from app.models.medical_interaction import MedicalInteraction

    target_user_message_id = chat_message_id

    mi = (
        db.query(MedicalInteraction)
        .filter(
            MedicalInteraction.chat_message_id == chat_message_id,
            MedicalInteraction.user_id == current_user.id,
        )
        .first()
    )

    if mi is None:
        msg = db.query(ChatMessage).filter(ChatMessage.id == chat_message_id).first()
        if not msg:
            raise HTTPException(status_code=404, detail="Chat message not found")

        if msg.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Not authorized")

        prev_user_msg = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.conversation_id == msg.conversation_id,
                ChatMessage.role == "user",
                or_(
                    ChatMessage.created_at < msg.created_at,
                    and_(
                        ChatMessage.created_at == msg.created_at,
                        ChatMessage.id < msg.id,
                    ),
                ),
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .first()
        )

        if not prev_user_msg:
            raise HTTPException(status_code=404, detail="No previous user message found to explain")

        target_user_message_id = prev_user_msg.id

        mi = (
            db.query(ChatMessage)
            .join(MedicalInteraction, MedicalInteraction.chat_message_id == ChatMessage.id)
            .filter(
                MedicalInteraction.chat_message_id == target_user_message_id,
                MedicalInteraction.user_id == current_user.id,
            )
            .with_entities(MedicalInteraction)
            .first()
        )

    if mi is None:
        raise HTTPException(status_code=404, detail="No medical explanation found for this message")

    extra = get_explanation_for_message(
        db=db,
        chat_message_id=target_user_message_id,
        user_id=current_user.id,
    ) or {}

    if not isinstance(extra, dict):
        extra = dict(extra)

    payload = {
        "chat_message_id": target_user_message_id,
        "risk_level": mi.risk_level,
        "emergency_detected": mi.emergency_detected,
        "risk_reason": mi.risk_reason,
        "risk_trigger": mi.risk_trigger,
        "primary_domain": mi.primary_domain,
        "all_domains": mi.all_domains,
        "model_name": mi.model_name,
        "created_at": mi.created_at,
        "confidence_score": extra.get("confidence_score", mi.confidence_score),
        "reasoning_summary": extra.get("reasoning_summary", mi.reasoning_summary),
    }

    return ExplainResponse(**payload)


@router.get("/chat/{chat_message_id}/explain-rag")
def explain_rag(
    chat_message_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.models.chat_message import ChatMessage

    msg = db.query(ChatMessage).filter(ChatMessage.id == chat_message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Chat message not found")

    if msg.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return {
        "chat_message_id": msg.id,
        "role": msg.role,
        "rag": (msg.meta or {}).get("rag"),
    }














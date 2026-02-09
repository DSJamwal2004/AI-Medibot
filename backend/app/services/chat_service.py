from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List, TYPE_CHECKING
if TYPE_CHECKING:
    from app.services.ai_service import generate_ai_reply

from datetime import datetime

from app.models.conversation import Conversation
from app.models.chat_message import ChatMessage
from app.models.doctor_escalation import DoctorEscalation
from app.models.medical_interaction import MedicalInteraction

from app.services.medical_safety import assess_medical_risk, RiskLevel, SafetySignal
from app.services.symptom_router import infer_medical_domain, infer_medical_domains
from app.services.medical_interaction_service import save_medical_interaction
from app.services.escalation_rules import should_escalate

from app.services.conversation_state import (
    infer_conversation_phase,
    extract_slots,
    missing_slots,
)

from app.services.clarification import generate_clarification_question

def retrieve_context_safe(**kwargs):
    from app.services.rag_service import retrieve_context
    return retrieve_context(**kwargs)


def get_collected_slots_from_conversation(
    db: Session,
    conversation_id: int,
) -> Dict[str, str]:
    """
    Merge slots collected across the conversation.
    """
    interactions = (
        db.query(MedicalInteraction)
        .filter(MedicalInteraction.conversation_id == conversation_id)
        .order_by(MedicalInteraction.created_at.asc())
        .all()
    )

    merged: Dict[str, str] = {}
    for mi in interactions:
        if mi.slots_collected:
            merged.update(mi.slots_collected)

    return merged


def clarification_already_asked(
    db: Session,
    conversation_id: int,
) -> bool:
    """
    Check if clarification was already performed in this conversation.
    """
    return (
        db.query(MedicalInteraction)
        .filter(
            MedicalInteraction.conversation_id == conversation_id,
            MedicalInteraction.conversation_phase == "clarification",
        )
        .count()
        > 0
    )

def conversation_has_red_risk(db: Session, conversation_id: int) -> bool:
    """
    Returns True if ANY interaction in the conversation was classified as RED risk.
    """
    return (
        db.query(MedicalInteraction)
        .filter(
            MedicalInteraction.conversation_id == conversation_id,
            MedicalInteraction.risk_level == RiskLevel.RED.value,
        )
        .count()
        > 0
    )

def get_primary_domain_from_conversation(
    db: Session,
    conversation_id: int,
) -> Optional[str]:
    """
    Returns the primary medical domain established at the start of the conversation.
    """
    mi = (
        db.query(MedicalInteraction)
        .filter(
            MedicalInteraction.conversation_id == conversation_id,
            MedicalInteraction.primary_domain.isnot(None),
        )
        .order_by(MedicalInteraction.created_at.asc())
        .first()
    )

    if mi:
        return mi.primary_domain

    return None

def is_emergency_followup(message: str) -> bool:
    t = (message or "").lower()
    followups = [
        "what should i do",
        "help me",
        "what now",
        "should i call",
        "is this serious",
        "what happens",
    ]
    return any(p in t for p in followups)


# ------------------------------------------------------------------
# Legacy intent helpers (imported by chat API)
# ------------------------------------------------------------------

def is_informational_message(message: str) -> bool:
    text = (message or "").lower()
    informational_phrases = [
        "what are", "what is", "what causes", "warning signs of",
        "symptoms of", "signs of", "causes of", "how does", "explain",
        "what happens", "how to know", "how do i know",
    ]
    return any(p in text for p in informational_phrases)


def is_high_severity_topic(message: str) -> bool:
    t = (message or "").lower()
    high_severity_topics = [
        "stroke", "heart attack", "myocardial infarction", "seizure",
        "pulmonary embolism", "blood clot", "aneurysm",
    ]
    return any(k in t for k in high_severity_topics)


# ------------------------------------------------------------------
# Conversation title generation
# ------------------------------------------------------------------

def generate_conversation_title(text: str, max_words: int = 6) -> str:
    words = text.strip().split()
    return " ".join(words[:max_words]).capitalize()


# ------------------------------------------------------------------
# Conversation lifecycle
# ------------------------------------------------------------------

def get_or_create_conversation(
    db: Session,
    user_id: int,
    conversation_id: Optional[int] = None,
) -> Conversation:
    if conversation_id:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .first()
        )
        if conversation:
            return conversation

    conversation = Conversation(user_id=user_id)
    db.add(conversation)
    return conversation


# ------------------------------------------------------------------
# Message persistence
# ------------------------------------------------------------------

def save_message(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    role: str,
    content: str,
) -> ChatMessage:
    message = ChatMessage(
        user_id=user_id,
        conversation_id=conversation_id,
        role=role,
        content=content,
    )
    db.add(message)

    if role == "user":
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user_id,
            )
            .first()
        )
        if conversation and not conversation.title:
            conversation.title = generate_conversation_title(content)

    return message


# ------------------------------------------------------------------
# Medical-aware message analysis
# ------------------------------------------------------------------

def analyze_user_message(message: str) -> Dict[str, Any]:
    safety_signal: SafetySignal = assess_medical_risk(message)

    primary_domain, domain_reason = infer_medical_domain(message)
    all_domains = infer_medical_domains(message)

    emergency_detected = safety_signal.risk_level == RiskLevel.RED

    return {
        "risk_level": safety_signal.risk_level.value,
        "risk_reason": safety_signal.reason,
        "risk_trigger": safety_signal.triggered_keyword,
        "primary_domain": primary_domain or "general",
        "domain_reason": domain_reason,
        "all_domains": all_domains,
        "emergency_detected": emergency_detected,
        "requires_escalation": emergency_detected,
    }


# ------------------------------------------------------------------
# Conversation history
# ------------------------------------------------------------------

def get_conversation_history(
    db: Session,
    *,
    conversation_id: int,
    limit: int = 10,
) -> List[Dict[str, str]]:
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in messages]


# ------------------------------------------------------------------
# Main chat processor
# ------------------------------------------------------------------

def process_chat_message(
    db: Session,
    *,
    user_id: int,
    conversation_id: Optional[int],
    message: str,
    is_greeting,
    is_thanks,
    is_goodbye,
    is_capability_query,
    is_vague_followup,
    has_explicit_condition,
    is_medication_query,
    get_citation_suppression_reason,
    get_last_domain_from_db,
) -> Dict[str, Any]:
    
    from app.services.ai_service import generate_ai_reply

    # 1️⃣ conversation
    conversation = get_or_create_conversation(db, user_id, conversation_id)
    db.flush()

    # 2️⃣ save USER message
    user_msg = save_message(
        db=db,
        user_id=user_id,
        conversation_id=conversation.id,
        role="user",
        content=message,
    )
    db.flush()

    # 3️⃣ deterministic analysis
    analysis = analyze_user_message(message)

    # ---------- intent detection ----------
    is_info = is_informational_message(message)

    primary_domain_locked = get_primary_domain_from_conversation(
        db, conversation.id
    )

    if (
        primary_domain_locked
        and primary_domain_locked != "general"
        and not is_info
    ):
        analysis["primary_domain"] = primary_domain_locked

    previous_slots = get_collected_slots_from_conversation(db, conversation.id)
    current_slots = extract_slots(message)
    merged_slots = {**previous_slots, **current_slots}
    missing = missing_slots(merged_slots)

    if is_info and analysis["risk_level"] != RiskLevel.RED.value:
        analysis["emergency_detected"] = False
        analysis["requires_escalation"] = False

    phase = infer_conversation_phase(
        message=message,
        analysis=analysis,
        is_greeting=is_greeting,
        is_goodbye=is_goodbye,
        is_vague_followup=is_vague_followup,
        has_escalation=False,
    )

    # Hard lock: once clarification happened, never re-enter it
    if clarification_already_asked(db, conversation.id):
        phase = "answering"


    save_medical_interaction(
        db=db,
        user_id=user_id,
        conversation_id=conversation.id,
        chat_message_id=user_msg.id,
        analysis=analysis,
        conversation_phase=phase,
        slots_collected=merged_slots,
    )

    skip_clarification = (
        is_vague_followup(message)
        or is_info
    )

    # ---------- clarification gate ----------

    should_clarify = (
        phase in ("info_gathering", "clarification")
        and not analysis["emergency_detected"]
        and not skip_clarification
        and missing
        and not clarification_already_asked(db, conversation.id)
    )

    if should_clarify:
        clarification_question = generate_clarification_question(
            missing_slots=missing,
            primary_domain=analysis["primary_domain"],
        )

        mi = (
            db.query(MedicalInteraction)
            .filter(MedicalInteraction.chat_message_id == user_msg.id)
            .first()
        )
        if mi:
            mi.conversation_phase = "clarification"
            mi.slots_collected = merged_slots

        assistant_msg = save_message(
            db=db,
            user_id=user_id,
            conversation_id=conversation.id,
            role="assistant",
            content=clarification_question,
        )

        db.commit()

        return {
            "conversation_id": conversation.id,
            "assistant_message_id": assistant_msg.id,
            "reply": clarification_question,
            "citations": [],
            "analysis": analysis,
            "confidence_score": 0.9,
            "suppression_reason": "clarification_required",
            "model_mode": "deterministic",
        }

    # 4️⃣ escalation rules
    should_flag, escalation_reason = should_escalate(
        is_emergency=analysis["emergency_detected"],
        risk_level=analysis["risk_level"],
        confidence_score=analysis.get("confidence_score", 0.5),
    )

    if should_flag:
        db.add(
            DoctorEscalation(
                user_id=user_id,
                conversation_id=conversation.id,
                reason=escalation_reason,
                notes=analysis["risk_reason"],
            )
        )
        conversation.ended_at = datetime.utcnow()

        mi = (
            db.query(MedicalInteraction)
            .filter(MedicalInteraction.chat_message_id == user_msg.id)
            .first()
        )
        if mi:
            mi.conversation_phase = "escalated"

    # 5️⃣ history
    history = get_conversation_history(db, conversation_id=conversation.id)

    msg_text = message or ""

    ai_reply = ""
    citations = []
    suppression_reason: Optional[str] = None
    rag_confidence = 0.0
    contexts = []
    model_confidence = 0.5
    reasoning_summary = ""
    model_mode = "offline"

    # ---------- intent gates ----------
    if is_greeting(msg_text):
        ai_reply = "Hi 👋 I’m AI Medibot.\n\nHow can I help you today?"
        suppression_reason = "non_medical_greeting"
        model_confidence = 0.9

    elif is_thanks(msg_text):
        ai_reply = "You’re welcome 🙂 Tell me your symptoms if you need help."
        suppression_reason = "non_medical_thanks"
        model_confidence = 0.85

    elif is_goodbye(msg_text):
        ai_reply = "Take care 👋 If symptoms worsen, consult a doctor."
        suppression_reason = "non_medical_goodbye"
        model_confidence = 0.85

    elif is_capability_query(msg_text):
        ai_reply = "I can help with symptoms, conditions, and medication safety."
        suppression_reason = "non_medical_capability"
        model_confidence = 0.9

    elif analysis["emergency_detected"]:
        suppression_reason = "emergency_override"
        ai_reply, _, _, model_confidence, reasoning_summary, model_mode = generate_ai_reply(
            msg_text,
            history,
            [],
            emergency_detected=True,
            emergency_trigger=analysis.get("risk_trigger"),
        )

    else:
        rag_query = msg_text
        effective_domain = analysis["primary_domain"]

        if effective_domain in (None, "general"):
            last_domain = get_last_domain_from_db(db, conversation.id)
            if last_domain:
                effective_domain = last_domain

        if is_vague_followup(msg_text):
            for h in reversed(history):
                if h["role"] == "user" and h["content"]:
                    rag_query = f"{h['content']}\n\nFollow-up question: {msg_text}"
                    break

        rag = retrieve_context_safe(
            query=rag_query,
            medical_domain=None if effective_domain in (None, "general") else effective_domain,
            is_emergency=False,
            min_authority_level=None,
            db=db,
        )

        rag_confidence = rag.confidence

        for c in rag.chunks or []:
            if c.get("content"):
                contexts.append(c["content"])
            if c.get("citation"):
                citations.append(c["citation"])

        if rag_confidence is not None and rag_confidence < 0.35:
            contexts = []
            citations = []
            suppression_reason = "low_rag_confidence"
        else:
            suppression_reason = get_citation_suppression_reason(
                msg_text, analysis, rag.chunks or []
            )
            if suppression_reason:
                citations = []

        ai_reply, _, _, model_confidence, reasoning_summary, model_mode = generate_ai_reply(
            msg_text,
            history,
            contexts,
            emergency_detected=False,
            emergency_trigger=analysis.get("risk_trigger"),
        )

    # ---------- final confidence ----------
    if suppression_reason and suppression_reason.startswith("non_medical_"):
        confidence_score = model_confidence
    else:
        confidence_score = (
            model_confidence
            if is_vague_followup(msg_text)
            else min(model_confidence, rag_confidence)
            if rag_confidence is not None
            else model_confidence
        )

    mi = (
        db.query(MedicalInteraction)
        .filter(MedicalInteraction.chat_message_id == user_msg.id)
        .first()
    )
    if mi:
        mi.confidence_score = float(confidence_score)
        mi.reasoning_summary = reasoning_summary

    assistant_msg = save_message(
        db=db,
        user_id=user_id,
        conversation_id=conversation.id,
        role="assistant",
        content=ai_reply,
    )

    assistant_msg.meta = assistant_msg.meta or {}
    assistant_msg.meta["rag"] = {
        "rag_confidence": rag_confidence,
        "model_confidence": model_confidence,
        "final_confidence": confidence_score,
        "citations_returned": bool(citations),
        "suppression_reason": suppression_reason,
    }

    db.commit()

    return {
        "conversation_id": conversation.id,
        "assistant_message_id": assistant_msg.id,
        "reply": ai_reply,
        "citations": citations,
        "analysis": analysis,
        "confidence_score": confidence_score,
        "suppression_reason": suppression_reason,
        "model_mode": model_mode,
    }







from sqlalchemy.orm import Session

from app.models.medical_interaction import MedicalInteraction


def save_medical_interaction(
    db: Session,
    *,
    user_id: int,
    conversation_id: int,
    chat_message_id: int,
    analysis: dict,
    conversation_phase: str | None = None,
    slots_collected: dict | None = None,
) -> MedicalInteraction:
    interaction = MedicalInteraction(
        user_id=user_id,
        conversation_id=conversation_id,
        chat_message_id=chat_message_id,
        risk_level=analysis["risk_level"],
        risk_reason=analysis["risk_reason"],
        risk_trigger=analysis.get("risk_trigger"),
        primary_domain=analysis["primary_domain"],
        all_domains=analysis["all_domains"],
        emergency_detected=analysis["requires_escalation"],
        model_name="deterministic-safety+rag",

        # 🆕 conversation intelligence
        conversation_phase=conversation_phase,
        slots_collected=slots_collected,
    )

    db.add(interaction)
    return interaction

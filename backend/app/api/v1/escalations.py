from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.doctor_escalation import DoctorEscalation
from app.core.dependencies import get_current_user
from app.models.user import User

router = APIRouter()


@router.get("/escalations")
def list_escalations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List doctor escalations for the current user.
    (Later this can be expanded to admin/doctor views.)
    """

    escalations = (
        db.query(DoctorEscalation)
        .filter(DoctorEscalation.user_id == current_user.id)
        .order_by(DoctorEscalation.created_at.desc())
        .all()
    )

    return [
        {
            "id": e.id,
            "conversation_id": e.conversation_id,
            "reason": e.reason,
            "notes": e.notes,
            "resolved": e.resolved,
            "created_at": e.created_at,
        }
        for e in escalations
    ]

@router.patch("/escalations/{escalation_id}/resolve")
def resolve_escalation(
    escalation_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Mark an escalation as resolved (handled by doctor/admin).
    Only allows resolving escalations that belong to the current user
    (can be relaxed later for admin/doctor roles).
    """

    escalation = (
        db.query(DoctorEscalation)
        .filter(
            DoctorEscalation.id == escalation_id,
            DoctorEscalation.user_id == current_user.id,
        )
        .first()
    )

    if not escalation:
        raise HTTPException(status_code=404, detail="Escalation not found")

    escalation.resolved = True
    db.add(escalation)
    db.commit()
    db.refresh(escalation)

    return {
        "id": escalation.id,
        "resolved": escalation.resolved,
    }
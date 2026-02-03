from app.db.session import SessionLocal
from app.models.doctor_escalation import DoctorEscalation


def test_doctor_escalation_created_on_emergency(client, auth_headers):
    response = client.post(
        "/api/v1/chat",
        json={"message": "I have severe chest pain and trouble breathing"},
        headers=auth_headers,
    )

    assert response.status_code == 200

    conversation_id = response.json()["conversation_id"]

    db = SessionLocal()
    try:
        escalations = (
            db.query(DoctorEscalation)
            .filter(DoctorEscalation.conversation_id == conversation_id)
            .all()
        )

        assert len(escalations) == 1

        escalation = escalations[0]
        assert escalation.reason
        assert escalation.resolved is False
    finally:
        db.close()


from app.services.ai_service import generate_ai_reply


def test_confidence_and_reasoning_present():
    reply, is_emergency, risk, confidence, reasoning = generate_ai_reply(
        "I have a mild headache",
        history=[],
    )

    assert 0.0 <= confidence <= 1.0
    assert confidence < 1.0
    assert isinstance(reasoning, str)
    assert len(reasoning.strip()) > 0


def test_emergency_has_high_confidence_and_reasoning(monkeypatch):
    # Force emergency detection
    def fake_detect(_):
        return True

    monkeypatch.setattr(
        "app.services.ai_service.detect_emergency",
        fake_detect,
    )

    reply, is_emergency, risk, confidence, reasoning = generate_ai_reply(
        "I have chest pain",
        history=[],
    )

    assert is_emergency is True
    assert risk == "high"
    assert confidence >= 0.9
    assert "emergency" in reply.lower()
    assert "rule" in reasoning.lower()

from app.services.ai_service import generate_ai_reply


def test_emergency_bypasses_llm(monkeypatch):
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


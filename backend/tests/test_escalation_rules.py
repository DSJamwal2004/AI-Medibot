from app.services.escalation_rules import should_escalate


def test_emergency_always_escalates():
    should_flag, reason = should_escalate(
        is_emergency=True,
        risk_level="high",
        confidence_score=0.9,
    )

    assert should_flag is True
    assert "emergency" in reason


def test_low_confidence_escalates():
    should_flag, reason = should_escalate(
        is_emergency=False,
        risk_level="low",
        confidence_score=0.3,
    )

    assert should_flag is True
    assert "confidence" in reason


def test_safe_case_does_not_escalate():
    should_flag, reason = should_escalate(
        is_emergency=False,
        risk_level="low",
        confidence_score=0.8,
    )

    assert should_flag is False
    assert reason == ""

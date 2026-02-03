def should_escalate(*, is_emergency: bool, risk_level: str, confidence_score: float):
    if is_emergency:
        return True, "emergency detected"

    if risk_level == "red":
        return True, "high medical risk"

    # ❌ REMOVE confidence-based escalation
    return False, ""


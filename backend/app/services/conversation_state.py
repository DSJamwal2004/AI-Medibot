import re

def is_informational_query(message: str) -> bool:
    text = (message or "").lower()
    informational_phrases = [
        "what is", "what are", "symptoms of", "causes of",
        "how does", "how do i", "explain", "tell me about"
    ]
    return any(p in text for p in informational_phrases)

def infer_conversation_phase(
    *,
    message: str,
    analysis: dict,
    is_greeting,
    is_goodbye,
    is_vague_followup,
    has_escalation: bool,
) -> str:
    if has_escalation:
        return "escalated"

    if is_goodbye(message):
        return "closed"

    if is_greeting(message):
        return "opening"

    if analysis.get("risk_level") == "red" and not is_informational_query(message):
        return "risk_assessment"

    if is_vague_followup(message):
        return "clarification"

    return "info_gathering"


def extract_slots(message: str) -> dict:
    msg = (message or "").lower()

    slots = {}

    if re.search(r"\b(years?|yo|yrs?)\b", msg):
        slots["age"] = "mentioned"

    if any(w in msg for w in ["days", "weeks", "months", "hours"]):
        slots["duration"] = "mentioned"

    if any(w in msg for w in ["mild", "moderate", "severe", "worst"]):
        slots["severity"] = "mentioned"

    if any(w in msg for w in ["worse", "worsening", "better", "improving"]):
        slots["progression"] = "mentioned"

    return slots


REQUIRED_SLOTS = ["symptom", "duration", "severity"]

def missing_slots(collected: dict) -> list[str]:
    return [s for s in REQUIRED_SLOTS if not collected.get(s)]

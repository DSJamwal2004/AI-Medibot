from enum import Enum
from dataclasses import dataclass
from typing import Optional


# ------------------------------------------------------------------
# Emergency symptom phrases (ALWAYS emergency)
# These represent current dangerous symptoms, not just topics.
# ------------------------------------------------------------------

EMERGENCY_SYMPTOM_KEYWORDS = {
    # Cardiac / breathing
    "chest pain",
    "chest tightness",
    "difficulty breathing",
    "trouble breathing",
    "can't breathe",
    "cannot breathe",
    "shortness of breath",
    "breathing problem",
    "severe shortness of breath",

    # Neuro emergencies
    "unconscious",
    "loss of consciousness",
    "fainted",
    "fainting",
    "seizure",
    "slurred speech",
    "face droop",
    "one-sided weakness",
    "weakness on one side",
    "sudden weakness",

    # Bleeding emergencies
    "bleeding heavily",
    "severe bleeding",
    "heavy bleeding",
    "bleeding a lot",
    "vomiting blood",
    "throwing up blood",
    "blood in vomit",
    "black stools",
    "tarry stools",

    # Severe allergic reaction / anaphylaxis
    "throat swelling",
    "swollen throat",
    "lip swelling",
    "lips swelling",
    "face swelling",
    "swelling and cannot breathe",
    "swelling and can't breathe",

    # Poisoning / overdose
    "overdose",
    "took too much",
    "poisoning",

    # Severe pain (kept but slightly risky: it can over-trigger; still ok for safety)
    "severe pain",
}

# ------------------------------------------------------------------
# High-severity medical topics (emergency ONLY if user is experiencing it)
# These are serious topics but not necessarily an active emergency.
# ------------------------------------------------------------------

HIGH_SEVERITY_TOPIC_KEYWORDS = {
    "stroke",
    "heart attack",
}

# ------------------------------------------------------------------
# Self-harm intent (ALWAYS emergency)
# ------------------------------------------------------------------

SELF_HARM_KEYWORDS = {
    "suicidal",
    "kill myself",
    "self harm",
}

# ------------------------------------------------------------------
# Special context-based emergency rules (simple + safe)
# ------------------------------------------------------------------

PREGNANCY_KEYWORDS = {"pregnant", "pregnancy"}
PREGNANCY_EMERGENCY_KEYWORDS = {
    "heavy bleeding",
    "bleeding heavily",
    "severe abdominal pain",
    "severe pain",
}

PEDIATRIC_KEYWORDS = {"baby", "infant", "newborn", "3 month old", "3-month-old"}
PEDIATRIC_EMERGENCY_KEYWORDS = {
    "not feeding",
    "not eating",
    "very sleepy",
    "lethargic",
    "high fever",
}

# ------------------------------------------------------------------
# Informational intent detection
# ------------------------------------------------------------------

INFORMATIONAL_PHRASES = {
    "what are",
    "what is",
    "what causes",
    "warning signs of",
    "symptoms of",
    "signs of",
    "causes of",
    "how does",
    "explain",
}

def is_informational_query(message: str) -> bool:
    text = (message or "").lower()
    return any(phrase in text for phrase in INFORMATIONAL_PHRASES)


# ------------------------------------------------------------------
# Risk modeling
# ------------------------------------------------------------------

class RiskLevel(str, Enum):
    GREEN = "green"   # informational / low risk
    AMBER = "amber"   # caution (reserved for future)
    RED = "red"       # emergency


@dataclass
class SafetySignal:
    risk_level: RiskLevel
    triggered_keyword: Optional[str]
    reason: str


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

def assess_medical_risk(message: str) -> SafetySignal:
    """
    Assess medical risk in a deterministic and explainable way.

    Option 2 UX:
    - Informational queries about severe topics (e.g., "warning signs of stroke")
      should NOT be treated as emergency.
    - Emergency symptom phrases (e.g., "chest pain") should still trigger emergency.
    - Self-harm intent is ALWAYS emergency.
    """
    text = (message or "").lower().strip()
    informational = is_informational_query(text)

    # 1) Self-harm intent is ALWAYS emergency
    for keyword in SELF_HARM_KEYWORDS:
        if keyword in text:
            return SafetySignal(
                risk_level=RiskLevel.RED,
                triggered_keyword=keyword,
                reason="Self-harm risk detected"
            )

    # 2) Pregnancy context emergency (simple rule)
    if any(k in text for k in PREGNANCY_KEYWORDS):
        for k in PREGNANCY_EMERGENCY_KEYWORDS:
            if k in text:
                return SafetySignal(
                    risk_level=RiskLevel.RED,
                    triggered_keyword=k,
                    reason="Pregnancy red-flag symptom detected"
                )

    # 3) Pediatric context emergency (simple rule)
    if any(k in text for k in PEDIATRIC_KEYWORDS):
        for k in PEDIATRIC_EMERGENCY_KEYWORDS:
            if k in text:
                return SafetySignal(
                    risk_level=RiskLevel.RED,
                    triggered_keyword=k,
                    reason="Pediatric red-flag symptom detected"
                )

    # 4) Emergency symptom phrases are ALWAYS emergency
    for keyword in EMERGENCY_SYMPTOM_KEYWORDS:
        if keyword in text:
            return SafetySignal(
                risk_level=RiskLevel.RED,
                triggered_keyword=keyword,
                reason="Emergency symptom detected"
            )

    # 5) High-severity topics (stroke/heart attack) are emergency only if NOT informational
    for keyword in HIGH_SEVERITY_TOPIC_KEYWORDS:
        if keyword in text:
            if informational:
                return SafetySignal(
                    risk_level=RiskLevel.GREEN,
                    triggered_keyword=None,
                    reason="Informational query about a high-severity topic"
                )
            return SafetySignal(
                risk_level=RiskLevel.RED,
                triggered_keyword=keyword,
                reason="High-severity topic mentioned in a non-informational context"
            )

    # 6) Informational queries default to GREEN
    if informational:
        return SafetySignal(
            risk_level=RiskLevel.GREEN,
            triggered_keyword=None,
            reason="Informational medical query"
        )

    # 7) Default safe state
    return SafetySignal(
        risk_level=RiskLevel.GREEN,
        triggered_keyword=None,
        reason="No emergency indicators detected"
    )


# ------------------------------------------------------------------
# Backward compatibility (DO NOT REMOVE)
# ------------------------------------------------------------------

def detect_emergency(message: str) -> bool:
    signal = assess_medical_risk(message)
    return signal.risk_level == RiskLevel.RED


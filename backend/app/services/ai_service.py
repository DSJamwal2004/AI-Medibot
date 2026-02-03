from __future__ import annotations

import json
import re
from typing import Optional

from app.services.medical_safety import detect_emergency as _detect_emergency
from app.core.config import settings

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # type: ignore

try:
    import requests
except Exception:
    requests = None  # type: ignore


SYSTEM_PROMPT = """
You are an AI medical assistant.
You are NOT a doctor.

Rules:
- Never give a diagnosis
- Never prescribe medication
- Never claim certainty
- Always recommend consulting a licensed doctor
- Escalate emergencies immediately
""".strip()


STRUCTURED_FORMAT_RULES = """
Output format (strict):
1) **What this could mean (general):**
- ...
2) **What you can do now (safe steps):**
- ...
3) **Red flags — seek urgent care now if:**
- ...
4) **To help me guide you, reply with:**
- ...
""".strip()


def detect_emergency(message: str) -> bool:
    """
    Backward-compatible emergency detector.

    Tests and older code monkeypatch this function.
    Real emergency detection lives in medical_safety.py.
    """
    return _detect_emergency(message)


def _emergency_ux_message(trigger: Optional[str] = None) -> str:
    trig = (trigger or "These symptoms").strip()
    return (
        f"⚠️ {trig.title()} can be a medical emergency.\n\n"
        "Please get urgent medical help now:\n"
        "- Call your local emergency number immediately\n"
        "- If possible, do NOT drive yourself — ask someone to help you get care\n\n"
        "Quick check (reply with yes/no):\n"
        "1) Trouble breathing or severe shortness of breath?\n"
        "2) Fainting, severe dizziness, or confusion?\n"
        "3) Sweating, nausea/vomiting, or feeling very weak?\n"
        "4) Pain spreading to arm/jaw/back OR sudden weakness on one side?\n"
        "5) Did it start suddenly or get worse quickly?\n\n"
        "If any answer is YES, treat this as urgent right now."
    )


# Lazy singleton OpenAI client (only created if OPENAI_API_KEY exists)
_client: Optional["OpenAI"] = None


def _get_openai_client() -> Optional["OpenAI"]:
    global _client

    if not getattr(settings, "OPENAI_API_KEY", None):
        return None

    if OpenAI is None:
        return None

    if _client is None:
        _client = OpenAI(api_key=settings.OPENAI_API_KEY)

    return _client


def _get_hf_token() -> Optional[str]:
    return getattr(settings, "HF_API_TOKEN", None) or None


def _get_hf_model() -> str:
    return getattr(settings, "HF_MODEL", None) or "Qwen/Qwen2.5-7B-Instruct"


def _get_hf_timeout() -> float:
    try:
        return float(getattr(settings, "HF_TIMEOUT_SECONDS", None) or 25)
    except Exception:
        return 25.0


def _is_info_high_severity(message: str) -> bool:
    t = (message or "").lower()
    if any(p in t for p in ["warning signs", "signs of", "symptoms of", "what are the symptoms"]):
        if any(k in t for k in ["stroke", "heart attack", "seizure"]):
            return True
    return False


def _info_high_severity_reply(message: str) -> str:
    t = (message or "").lower()

    if "stroke" in t:
        return (
            "Warning signs of stroke (act FAST):\n\n"
            "FAST:\n"
            "- F: Face drooping\n"
            "- A: Arm weakness (one side)\n"
            "- S: Speech difficulty (slurred / unable to speak)\n"
            "- T: Time to call emergency services immediately\n\n"
            "Other possible warning signs:\n"
            "- Sudden numbness or weakness (especially one side)\n"
            "- Sudden confusion or trouble understanding\n"
            "- Sudden trouble seeing in one or both eyes\n"
            "- Sudden severe headache (worst headache) with no known cause\n"
            "- Sudden trouble walking, dizziness, loss of balance/coordination\n\n"
            "What to do right now:\n"
            "- Call emergency services immediately\n"
            "- Note the time symptoms started (or last known well)\n"
            "- Do not wait for symptoms to improve\n"
        )

    return (
        "Here are important warning signs to watch for:\n\n"
        "- Sudden or severe symptoms\n"
        "- Trouble breathing\n"
        "- Fainting or severe dizziness\n"
        "- New chest pain or pressure\n"
        "- Confusion, severe weakness, or one-sided symptoms\n\n"
        "If these happen, seek urgent medical care immediately."
    )


def _is_medication_query(message: str) -> bool:
    t = (message or "").lower()
    markers = [
        "can i take",
        "together",
        "with",
        "interaction",
        "side effect",
        "side effects",
        "dose",
        "dosage",
        "medicine",
        "medication",
        "drug",
        "tablet",
        "pill",
        "antibiotic",
        "antibiotics",
        "warfarin",
        "ibuprofen",
        "paracetamol",
        "acetaminophen",
        "metformin",
        "insulin",
    ]
    return any(m in t for m in markers)


def _dedupe_sentences(lines: list[str]) -> list[str]:
    """
    Remove near-duplicate bullets.
    """
    seen = set()
    out = []
    for s in lines:
        key = re.sub(r"\s+", " ", (s or "").strip().lower())
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def _clean_medquad_text(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"(?is)^question:\s.*?\nanswer:\s*", "", text).strip()
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _build_hf_messages(message: str, history: list[dict], context: list[str] | None) -> list[dict]:
    """
    Build OpenAI-style messages for HF Inference Providers API.
    """
    grounded_system = SYSTEM_PROMPT + "\n\n" + (
        "Grounding rules:\n"
        "- If medical context is provided, answer using ONLY that context.\n"
        "- If the context does not contain the answer, say you don't have enough reliable information.\n"
        "- Do NOT invent causes, treatments, or statistics.\n"
        "- Keep it short, practical, and safety-first.\n\n"
        f"{STRUCTURED_FORMAT_RULES}\n"
    )

    messages = [{"role": "system", "content": grounded_system}]

    if context and any((c or "").strip() for c in context):
        ctx_text = "\n\n---\n\n".join([c.strip() for c in context[:4] if (c or "").strip()])
        messages.append(
            {
                "role": "system",
                "content": "AUTHORITATIVE MEDICAL CONTEXT (use only this):\n\n" + ctx_text,
            }
        )

    # include last turns
    for m in (history or [])[-6:]:
        role = (m.get("role") or "").lower()
        content = (m.get("content") or "").strip()
        if not content:
            continue
        if role not in ("user", "assistant"):
            continue
        messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": message})
    return messages


def _call_hf_inference(messages: list[dict]) -> str:
    token = _get_hf_token()
    model = _get_hf_model()

    if not token:
        raise RuntimeError("HF_API_TOKEN not configured")

    if requests is None:
        raise RuntimeError("requests not installed")

    url = "https://router.huggingface.co/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 260,
    }

    timeout = _get_hf_timeout()
    r = requests.post(url, headers=headers, data=json.dumps(payload), timeout=timeout)

    if r.status_code >= 400:
        raise RuntimeError(f"HF chat failed: HTTP {r.status_code} - {r.text[:300]}")

    data = r.json()

    try:
        return (data["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        raise RuntimeError(f"HF chat returned unexpected payload: {str(data)[:300]}")


def generate_ai_reply(
    message: str,
    history: list[dict],
    context: list[str] | None = None,
    emergency_detected: bool = False,
    emergency_trigger: Optional[str] = None,
) -> tuple[str, bool, str, float, str, str]:
    """
    Returns:
    - reply: str
    - is_emergency: bool
    - risk_level: str
    - confidence_score: float (0.0 – 1.0)
    - reasoning_summary: str
    - model_mode: "online" | "offline"
    """

    # Backward compatible emergency detection (for tests / legacy callers)
    if not emergency_detected:
        try:
            emergency_detected = detect_emergency(message)
        except Exception:
            emergency_detected = False

    if emergency_detected:
        return (
            _emergency_ux_message(emergency_trigger),
            True,
            "red",
            0.95,
            "Emergency override rule triggered by safety detection.",
            "offline",  # ← added
        )

    if _is_info_high_severity(message):
        return (
            _info_high_severity_reply(message),
            False,
            "medium",
            0.75,
            "High-severity informational UX response template used.",
            "offline",  # ← added (template, not LLM)
        )

    has_context = bool(context and any((c or "").strip() for c in context))

    # -----------------------------
    # Online mode (Hugging Face first)
    # -----------------------------
    hf_token = _get_hf_token()
    if hf_token:
        try:
            msgs = _build_hf_messages(message=message, history=history, context=context)
            reply = _call_hf_inference(msgs)

            if not reply.strip():
                reply = "I don’t have enough reliable information to answer that safely. Please consult a licensed doctor."

            conf = 0.85 if has_context else 0.6

            return (
                reply,
                False,
                "medium",
                conf,
                f"Response generated using Hugging Face Inference API (model={_get_hf_model()}).",
                "online",  # ← added
            )

        except Exception as e:
            print("HF inference failed -> falling back offline:", str(e))

    # -----------------------------
    # Online mode (OpenAI optional)
    # -----------------------------
    client = _get_openai_client()
    if client is not None:
        grounded_system = SYSTEM_PROMPT + "\n\n" + (
            "Grounding rules:\n"
            "- If medical context is provided, answer ONLY using that context.\n"
            "- If the context does not contain the answer, say you don't have enough reliable information.\n"
            "- Do NOT invent symptoms, causes, treatments, or statistics.\n"
            "- Keep the answer short and practical.\n\n"
            f"{STRUCTURED_FORMAT_RULES}\n"
        )

        messages = [{"role": "system", "content": grounded_system}]

        if has_context:
            messages.append(
                {
                    "role": "system",
                    "content": (
                        "Medical context (authoritative). Use ONLY this to answer:\n\n"
                        + "\n\n---\n\n".join(context[:4])
                    ),
                }
            )

        messages.extend(history[-6:])
        messages.append({"role": "user", "content": message})

        try:
            model = getattr(settings, "OPENAI_MODEL", None) or "gpt-4o-mini"

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.2,
            )

            reply = response.choices[0].message.content or ""
            if not reply.strip():
                reply = "I don’t have enough reliable information to answer that safely. Please consult a licensed doctor."

            conf = 0.8 if has_context else 0.55

            return (
                reply,
                False,
                "medium",
                conf,
                "Response generated using OpenAI with strict RAG grounding.",
                "online",  # ← added
            )

        except Exception:
            pass  # fall through to offline

    # -----------------------------
    # Offline deterministic fallback
    # -----------------------------
    if context and any((c or "").strip() for c in context):
        cleaned = [_clean_medquad_text(c or "") for c in context[:8]]
        cleaned = [c for c in cleaned if c]

        short = []
        for c in cleaned[:6]:
            parts = [p.strip() for p in c.replace("\n", " ").split(".") if p.strip()]
            s = ". ".join(parts[:2]).strip()
            if s and not s.endswith("."):
                s += "."
            if s:
                short.append(s)

        short = _dedupe_sentences(short)

        if short:
            if _is_medication_query(message):
                reply = (
                    "Medication safety information from trusted sources:\n\n"
                    + "\n\n".join(f"- {s}" for s in short[:5])
                    + "\n\nIf this is about interactions or bleeding risk, confirm with your doctor/pharmacist."
                )
            else:
                reply = (
                    "Here’s what trusted medical sources say:\n\n"
                    + "\n\n".join(f"- {s}" for s in short[:5])
                    + "\n\nIf symptoms are severe or worsening, seek medical care."
                )
        else:
            reply = (
                "Based on trusted medical sources, I found some relevant information, "
                "but it may not directly answer your question.\n\n"
                "If symptoms are severe or worsening, seek medical care."
            )

        return (
            reply,
            False,
            "medium",
            0.75,
            "Offline mode: grounded response generated from retrieved medical context.",
            "offline",  # ← added
        )

    reply = (
        "I understand your concern. I can’t provide a diagnosis, but I can share general guidance.\n\n"
        "If your symptoms are severe, worsening, or you have red-flag signs (fainting, chest pain, "
        "confusion, weakness, trouble breathing), seek urgent medical care.\n\n"
        "To help, tell me:\n"
        "- Your age\n"
        "- How long this has been happening\n"
        "- Fever, vomiting, or dehydration?\n"
        "- Any medicines taken recently"
    )

    return (
        reply,
        False,
        "medium",
        0.5,
        "No cloud model available (HF/OpenAI); deterministic fallback response used.",
        "offline",  # ← added
    )









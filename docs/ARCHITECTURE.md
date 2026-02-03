# AI Medibot – System Architecture

This document describes the internal architecture and design decisions behind AI Medibot.

The system is designed with **healthcare safety, determinism, and explainability** as first-class concerns.

---

## 1. High-Level Architecture

User → Frontend (Next.js) → Backend (FastAPI) → PostgreSQL + pgvector

---

## 2. Request Lifecycle (Chat Message)

1. User sends a message from the UI
2. Message is stored as immutable conversation history
3. Deterministic medical safety rules are applied
4. Conversation phase is inferred (triage, clarification, etc.)
5. Emergency & escalation rules are evaluated
6. If safe, medical knowledge is retrieved (RAG)
7. AI response is generated (offline or online)
8. All decisions are logged for audit & explainability

---

## 3. Medical Safety Layer

- Rule-based (no LLM)
- Symptom-driven emergency detection
- Informational queries do not trigger emergencies
- Safety decisions are message-scoped (not sticky)

---

## 4. Conversation State

Each message is assigned a phase:
- opening
- risk_assessment
- info_gathering
- clarification
- answering
- escalated
- closed

This controls clarification prompts and escalation behavior.

---

## 5. Retrieval-Augmented Generation (RAG)

- Local embeddings: `sentence-transformers/all-MiniLM-L6-v2`
- Vector store: PostgreSQL + pgvector
- Domain-aware retrieval
- Citation-backed responses
- Explainable retrieval metadata

---

## 6. Online / Offline AI Strategy

- Offline deterministic mode (default)
- Optional online LLM (Hugging Face)
- Automatic fallback when online inference is unavailable

---

## 7. Audit & Explainability

Each interaction records:
- risk level
- trigger keywords
- confidence score
- reasoning summary
- retrieval metadata

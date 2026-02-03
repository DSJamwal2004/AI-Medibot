# AI Medibot 🏥🤖

AI Medibot is a healthcare-focused conversational AI system built with a strong emphasis on **medical safety, explainability, and reliability**.

This project goes beyond a typical chatbot by combining deterministic safety rules, explainable Retrieval-Augmented Generation (RAG), and structured conversation state management.

> ⚠️ **Medical Disclaimer**  
> AI Medibot is for informational purposes only and does not provide medical diagnosis.  
> In medical emergencies, users are instructed to seek professional healthcare immediately.

---

## 🚀 Key Features

### 🛡️ Medical Safety & Emergency Handling
- Deterministic emergency detection (e.g. chest pain, breathing difficulty)
- Explicit safety overrides
- Emergency escalation workflow
- Risk is evaluated per message (not permanently sticky)

### 🧠 Conversational Intelligence
- Multi-turn conversation memory
- Conversation phase modeling (triage, clarification, info)
- Slot extraction (symptom, duration, severity)
- Safe clarification logic

### 📚 Explainable Medical RAG
- Semantic retrieval using pgvector
- Local embeddings (MiniLM)
- Domain-aware medical filtering
- Citation-backed responses
- Explainability endpoints

### 🔌 Online + Offline AI
- Offline deterministic mode for safety
- Optional Hugging Face LLM support
- Automatic fallback if online inference fails

### 🧪 Evaluation & Testing
- Automated tests for safety & escalation
- Evaluation runner with predefined cases

---

## 🧱 Tech Stack

**Frontend**
- Next.js (App Router)
- TypeScript
- Tailwind CSS

**Backend**
- FastAPI
- SQLAlchemy
- Alembic
- PostgreSQL + pgvector

**AI**
- Sentence Transformers
- pgvector similarity search
- Hugging Face Inference API (optional)

---

## 📁 Project Structure




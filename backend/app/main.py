import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import auth, chat, health, conversations, escalations
from app.services.rag_service import _get_embedding_model


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("medibot")

app = FastAPI(title="AI MediBot")

logger.info("🚀 AI MediBot starting up")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://ai-medibot.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/readyz")
def ready():
    return {"ready": True}

@app.on_event("shutdown")
def on_shutdown():
    logger.info("🛑 AI MediBot shutting down")
    db = getattr(app.state, "db", None)
    if db:
        db.close()

app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(conversations.router, prefix="/api/v1", tags=["Conversations"])
app.include_router(escalations.router, prefix="/api/v1", tags=["Escalations"])




from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1 import auth, chat, health, conversations, escalations
from app.db.init_db import init_db
from app.db.session import SessionLocal

app = FastAPI(title="AI MediBot")

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

@app.on_event("startup")
def on_startup():
    # Initialize database tables
    init_db()

    # Create a shared DB session for integration tests
    app.state.db = SessionLocal()


@app.on_event("shutdown")
def on_shutdown():
    # Close DB session cleanly
    db = getattr(app.state, "db", None)
    if db:
        db.close()


# Routers
app.include_router(auth.router, prefix="/api/v1", tags=["Auth"])
app.include_router(chat.router, prefix="/api/v1", tags=["Chat"])
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(conversations.router, prefix="/api/v1", tags=["Conversations"])
app.include_router(escalations.router, prefix="/api/v1", tags=["Escalations"])



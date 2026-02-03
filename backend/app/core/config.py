from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --------------------
    # App
    # --------------------
    PROJECT_NAME: str = "AI MediBot"
    API_V1_STR: str = "/api/v1"

    # --------------------
    # Security / Auth
    # --------------------
    SECRET_KEY: str = "change_this_later"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --------------------
    # Database
    # --------------------
    DATABASE_URL: str

    # HUGGING FACE
    HF_API_TOKEN: str = ""
    HF_MODEL: str = "mistralai/Mistral-7B-Instruct-v0.2"
    HF_TIMEOUT_SECONDS: int = 25

    # Optional (future-proof: Ollama / Azure / LM Studio)
    OPENAI_BASE_URL: str | None = None

    # --------------------
    # RAG / Vector Store
    # --------------------
    VECTOR_BACKEND: Literal["memory", "pgvector"] = "memory"

    # (Optional) Only require OPENAI_API_KEY if you truly need it
    OPENAI_API_KEY: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # IMPORTANT: allows extra env vars like HF_HUB_...
    )

settings = Settings()




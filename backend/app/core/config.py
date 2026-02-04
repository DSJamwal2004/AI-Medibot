from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # --------------------
    # App
    # --------------------
    PROJECT_NAME: str = "AI MediBot"
    API_V1_STR: str = "/api/v1"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"

    # --------------------
    # Security / Auth
    # --------------------
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --------------------
    # Database
    # --------------------
    DATABASE_URL: str

    # --------------------
    # Hugging Face
    # --------------------
    HF_API_TOKEN: str = ""
    HF_MODEL: str = "mistralai/Mistral-7B-Instruct-v0.2"
    HF_TIMEOUT_SECONDS: int = 25

    # Optional (future-proof)
    OPENAI_BASE_URL: str | None = None
    OPENAI_API_KEY: str | None = None

    # --------------------
    # RAG / Vector Store
    # --------------------
    VECTOR_BACKEND: Literal["memory", "pgvector"] = "pgvector"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

settings = Settings()

if not settings.DATABASE_URL:
    raise RuntimeError("DATABASE_URL environment variable is required")





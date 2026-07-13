import logging
import os
from typing import List, Union
from pydantic import AnyHttpUrl, BeforeValidator, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing_extensions import Annotated


def parse_cors(v: Union[str, List[str]]) -> List[str]:
    if isinstance(v, str) and not v.startswith("["):
        return [i.strip() for i in v.split(",")]
    elif isinstance(v, (list, str)):
        return v
    raise ValueError(v)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ".env"
        ),
        env_ignore_empty=True,
        extra="ignore"
    )

    # ── API ──────────────────────────────────────────────────
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "PropVista AI"

    # ── CORS ─────────────────────────────────────────────────
    BACKEND_CORS_ORIGINS: Annotated[
    List[str], BeforeValidator(parse_cors)
] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "https://propvista-frontend.vercel.app",
]

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres"

    # ── Supabase ─────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""
    
    @property
    def SUPABASE_JWKS_URL(self) -> str:
        return f"{self.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"

    # ── Security ─────────────────────────────────────────────

    # ── AI — Groq (Stage 5) ───────────────────────────────────
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # ── Payments — Razorpay (Stage 3) ────────────────────────
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value:
            raise ValueError("DATABASE_URL must be set to a Supabase PostgreSQL connection string.")
        if "sqlite" in value.lower() or "aiosqlite" in value.lower():
            raise ValueError("DATABASE_URL cannot use SQLite; use Supabase PostgreSQL only.")
        
        # Let standard DNS handle resolution to automatically support IPv4 fallback
        return value

settings = Settings()

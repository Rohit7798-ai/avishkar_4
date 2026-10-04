import os
import json
from pathlib import Path
from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
# ponytail: on Vercel/serverless environments the root filesystem is read-only; fallback to /tmp
DEFAULT_DATA_DIR = Path("/tmp") if os.environ.get("VERCEL") else (PROJECT_ROOT / "data")
DEFAULT_DB_PATH = DEFAULT_DATA_DIR / "farmer_decision.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"



class Settings(BaseSettings):
    PROJECT_NAME: str = "farmer-decision-system"
    API_V1_STR: str = "/api"
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # CORS origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        elif isinstance(v, list):
            return v
        return []

    # Database configuration pointing to data/farmer_decision.db
    DATABASE_URL: str = DEFAULT_DATABASE_URL

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def validate_database_url(cls, v: Union[str, None]) -> str:
        if not v:
            return DEFAULT_DATABASE_URL
        if isinstance(v, str):
            # Normalize legacy postgres:// URI to postgresql:// for SQLAlchemy 2.0 compatibility
            if v.startswith("postgres://"):
                v = v.replace("postgres://", "postgresql://", 1)
            # On Vercel serverless, ensure file SQLite redirects to writable /tmp volume
            if os.environ.get("VERCEL") and v.startswith("sqlite"):
                if not v.startswith("sqlite:////tmp") and ":memory:" not in v:
                    return "sqlite:////tmp/farmer_decision.db"
        return v

    # External Provider Configuration
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1"
    OPEN_METEO_TIMEOUT_SECONDS: float = 10.0

    # External Market Provider (Government of India Open Government Data - data.gov.in)
    OGD_MANDI_API_URL: str = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
    OGD_API_KEY: Union[str, None] = None
    OGD_TIMEOUT_SECONDS: float = 10.0

    # Google Gemini LLM API Configuration
    GEMINI_API_KEY: Union[str, None] = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()


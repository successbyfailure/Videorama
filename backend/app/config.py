"""
Videorama v2.0.0 - Configuration
Application settings and environment variables
"""

from pydantic_settings import BaseSettings
from pydantic import field_validator
from typing import Optional, Union


class Settings(BaseSettings):
    """Application settings"""

    # Application
    APP_NAME: str = "Videorama"
    VERSION: str = "2.0.0"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://videorama:videorama@localhost:5432/videorama"

    # Storage
    STORAGE_BASE_PATH: str = "/home/user/Videorama/storage"

    # VHS Integration
    VHS_BASE_URL: str = "http://localhost:8000"
    VHS_TIMEOUT: int = 60

    # LLM Configuration
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o"

    # External APIs
    TMDB_API_KEY: Optional[str] = None
    SPOTIFY_CLIENT_ID: Optional[str] = None
    SPOTIFY_CLIENT_SECRET: Optional[str] = None

    # Telegram Bot
    TELEGRAM_BOT_TOKEN: Optional[str] = None

    # Security
    SECRET_KEY: str = "change-this-secret-key-in-production"

    # CORS
    CORS_ORIGINS: Union[list[str], str] = ["http://localhost:3000", "http://localhost:5173"]

    # Celery
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v):
        """Parse CORS_ORIGINS from comma-separated string or list"""
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()

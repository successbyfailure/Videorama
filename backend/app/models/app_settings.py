"""
Videorama v2.0.0 - Application Settings Model
Persisted settings managed via the UI
"""

from sqlalchemy import Column, String, Boolean, Integer, Float, Text
from ..database import Base
import time


class AppSettings(Base):
    """
    Persisted application settings (single row).
    Initialized from environment on first startup.
    """

    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, default=1)

    # Application
    app_name = Column(String, nullable=False, default="Videorama")
    version = Column(String, nullable=False, default="2.0.0")
    debug = Column(Boolean, default=False)

    # Storage
    storage_base_path = Column(String, nullable=False, default="/storage")

    # VHS
    vhs_base_url = Column(String, nullable=False, default="https://vhs.mksmad.org")
    vhs_timeout = Column(Integer, default=600)
    vhs_verify_ssl = Column(Boolean, default=True)

    # LLM
    openai_api_key = Column(Text)
    openai_base_url = Column(String, default="https://api.openai.com/v1")
    openai_model = Column(String, default="gpt-4o")

    # External APIs
    tmdb_api_key = Column(Text)
    spotify_client_id = Column(String)
    spotify_client_secret = Column(String)

    # Telegram
    telegram_bot_token = Column(String)

    # Timestamps
    created_at = Column(Float, default=lambda: time.time())
    updated_at = Column(Float, default=lambda: time.time(), onupdate=time.time)

    def __repr__(self):
        return f"<AppSettings(app_name={self.app_name}, version={self.version})>"

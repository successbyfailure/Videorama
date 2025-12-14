"""
Videorama v2.0.0 - Settings Service
Persist and retrieve application settings from the database.
"""

from sqlalchemy.orm import Session
import time
from typing import Optional

from ..models import AppSettings
from ..config import settings as env_settings


class SettingsService:
    """Persisted settings helper"""

    @staticmethod
    def get_settings(db: Session) -> AppSettings:
        """Return current settings, seeding from env if missing."""
        record = db.query(AppSettings).first()

        if not record:
            record = SettingsService._seed_from_env(db)

        # Ensure runtime config mirrors DB values
        SettingsService._apply_to_runtime_config(record)
        return record

    @staticmethod
    def update_settings(db: Session, updates: dict) -> AppSettings:
        """Update settings with provided fields."""
        record = SettingsService.get_settings(db)

        changed = False
        for key, value in updates.items():
            if value is None:
                continue
            if hasattr(record, key):
                setattr(record, key, value)
                changed = True

        if changed:
            record.updated_at = time.time()
            db.commit()
            db.refresh(record)
            SettingsService._apply_to_runtime_config(record)

        return record

    @staticmethod
    def _seed_from_env(db: Session) -> AppSettings:
        """Create initial settings row from environment-based config."""
        record = AppSettings(
            app_name=env_settings.APP_NAME,
            version=env_settings.VERSION,
            debug=env_settings.DEBUG,
            storage_base_path=env_settings.STORAGE_BASE_PATH,
            vhs_base_url=env_settings.VHS_BASE_URL,
            vhs_timeout=env_settings.VHS_TIMEOUT,
            vhs_verify_ssl=env_settings.VHS_VERIFY_SSL,
            openai_api_key=env_settings.OPENAI_API_KEY,
            openai_base_url=env_settings.OPENAI_BASE_URL,
            openai_model=env_settings.OPENAI_MODEL,
            tmdb_api_key=env_settings.TMDB_API_KEY,
            spotify_client_id=env_settings.SPOTIFY_CLIENT_ID,
            spotify_client_secret=env_settings.SPOTIFY_CLIENT_SECRET,
            telegram_bot_token=env_settings.TELEGRAM_BOT_TOKEN,
            created_at=time.time(),
            updated_at=time.time(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def _apply_to_runtime_config(record: AppSettings):
        """
        Mirror DB-backed values onto the in-memory config settings object.
        This keeps services using app.config.settings in sync after updates.
        """
        mapping = {
            "APP_NAME": record.app_name,
            "VERSION": record.version,
            "DEBUG": record.debug,
            "STORAGE_BASE_PATH": record.storage_base_path,
            "VHS_BASE_URL": record.vhs_base_url,
            "VHS_TIMEOUT": record.vhs_timeout,
            "VHS_VERIFY_SSL": record.vhs_verify_ssl,
            "OPENAI_API_KEY": record.openai_api_key,
            "OPENAI_BASE_URL": record.openai_base_url,
            "OPENAI_MODEL": record.openai_model,
            "TMDB_API_KEY": record.tmdb_api_key,
            "SPOTIFY_CLIENT_ID": record.spotify_client_id,
            "SPOTIFY_CLIENT_SECRET": record.spotify_client_secret,
            "TELEGRAM_BOT_TOKEN": record.telegram_bot_token,
        }

        for key, value in mapping.items():
            setattr(env_settings, key, value)

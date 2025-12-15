"""
Videorama v2.0.0 - Settings API
GET/UPDATE application settings
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from ...database import get_db
from ...services.settings_service import SettingsService

router = APIRouter()


class SettingsSchema(BaseModel):
    """Settings schema for API"""

    # Application
    app_name: str
    version: str
    debug: bool

    # Storage
    storage_base_path: str

    # VHS Integration
    vhs_base_url: str
    vhs_timeout: int
    vhs_verify_ssl: bool

    # LLM Configuration
    openai_api_key: Optional[str] = None
    openai_base_url: str
    openai_model: str

    # External APIs
    tmdb_api_key: Optional[str] = None
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None

    # Telegram Bot
    telegram_bot_token: Optional[str] = None


class SettingsUpdateSchema(BaseModel):
    """Settings update schema (all fields optional)"""

    app_name: Optional[str] = None
    debug: Optional[bool] = None
    storage_base_path: Optional[str] = None
    vhs_base_url: Optional[str] = None
    vhs_timeout: Optional[int] = None
    vhs_verify_ssl: Optional[bool] = None
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    tmdb_api_key: Optional[str] = None
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None
    telegram_bot_token: Optional[str] = None


@router.get("/app-settings", response_model=SettingsSchema)
async def get_settings(db: Session = Depends(get_db)):
    """Get current application settings from the database"""
    record = SettingsService.get_settings(db)

    return SettingsSchema(
        app_name=record.app_name,
        version=record.version,
        debug=record.debug,
        storage_base_path=record.storage_base_path,
        vhs_base_url=record.vhs_base_url,
        vhs_timeout=record.vhs_timeout,
        vhs_verify_ssl=record.vhs_verify_ssl,
        openai_api_key=_mask_secret(record.openai_api_key),
        openai_base_url=record.openai_base_url,
        openai_model=record.openai_model,
        tmdb_api_key=_mask_secret(record.tmdb_api_key),
        spotify_client_id=_mask_secret(record.spotify_client_id),
        spotify_client_secret=_mask_secret(record.spotify_client_secret),
        telegram_bot_token=_mask_secret(record.telegram_bot_token),
    )


@router.put("/app-settings", response_model=SettingsSchema)
async def update_settings(
    updates: SettingsUpdateSchema, db: Session = Depends(get_db)
):
    """
    Update application settings

    Persists to the database. Also mirrors changes to in-memory config for runtime use.
    """
    update_dict = updates.model_dump(exclude_none=True)
    record = SettingsService.update_settings(db, update_dict)

    return SettingsSchema(
        app_name=record.app_name,
        version=record.version,
        debug=record.debug,
        storage_base_path=record.storage_base_path,
        vhs_base_url=record.vhs_base_url,
        vhs_timeout=record.vhs_timeout,
        vhs_verify_ssl=record.vhs_verify_ssl,
        openai_api_key=_mask_secret(record.openai_api_key),
        openai_base_url=record.openai_base_url,
        openai_model=record.openai_model,
        tmdb_api_key=_mask_secret(record.tmdb_api_key),
        spotify_client_id=_mask_secret(record.spotify_client_id),
        spotify_client_secret=_mask_secret(record.spotify_client_secret),
        telegram_bot_token=_mask_secret(record.telegram_bot_token),
    )


def _mask_secret(value: Optional[str]) -> Optional[str]:
    """Mask secret values for API response"""
    if not value:
        return None

    if len(value) <= 8:
        return "***"

    return f"{value[:4]}***{value[-4:]}"

"""
Videorama v2.0.0 - Settings API
GET/UPDATE application settings
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import os
from pathlib import Path

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
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: Optional[str] = None
    tmdb_api_key: Optional[str] = None
    spotify_client_id: Optional[str] = None
    spotify_client_secret: Optional[str] = None
    telegram_bot_token: Optional[str] = None


@router.get("/settings", response_model=SettingsSchema)
async def get_settings():
    """Get current application settings"""
    from app.config import settings

    # Mask sensitive values for API response
    return SettingsSchema(
        app_name=settings.APP_NAME,
        version=settings.VERSION,
        debug=settings.DEBUG,
        storage_base_path=settings.STORAGE_BASE_PATH,
        vhs_base_url=settings.VHS_BASE_URL,
        vhs_timeout=settings.VHS_TIMEOUT,
        openai_api_key=_mask_secret(settings.OPENAI_API_KEY),
        openai_base_url=settings.OPENAI_BASE_URL,
        openai_model=settings.OPENAI_MODEL,
        tmdb_api_key=_mask_secret(settings.TMDB_API_KEY),
        spotify_client_id=_mask_secret(settings.SPOTIFY_CLIENT_ID),
        spotify_client_secret=_mask_secret(settings.SPOTIFY_CLIENT_SECRET),
        telegram_bot_token=_mask_secret(settings.TELEGRAM_BOT_TOKEN),
    )


@router.put("/settings", response_model=SettingsSchema)
async def update_settings(updates: SettingsUpdateSchema):
    """
    Update application settings

    NOTE: This updates the .env file. Changes require application restart.
    """
    env_path = Path(".env")

    if not env_path.exists():
        raise HTTPException(
            status_code=404,
            detail=".env file not found. Please create one from .env.example",
        )

    # Read current .env file
    env_lines = env_path.read_text().splitlines()

    # Mapping of schema fields to env var names
    field_to_env = {
        "app_name": "APP_NAME",
        "debug": "DEBUG",
        "storage_base_path": "STORAGE_BASE_PATH",
        "vhs_base_url": "VHS_BASE_URL",
        "vhs_timeout": "VHS_TIMEOUT",
        "openai_api_key": "OPENAI_API_KEY",
        "openai_base_url": "OPENAI_BASE_URL",
        "openai_model": "OPENAI_MODEL",
        "tmdb_api_key": "TMDB_API_KEY",
        "spotify_client_id": "SPOTIFY_CLIENT_ID",
        "spotify_client_secret": "SPOTIFY_CLIENT_SECRET",
        "telegram_bot_token": "TELEGRAM_BOT_TOKEN",
    }

    # Update env vars
    updated_lines = []
    updated_keys = set()

    for line in env_lines:
        line = line.rstrip()

        # Skip empty lines and comments
        if not line or line.startswith("#"):
            updated_lines.append(line)
            continue

        # Parse key=value
        if "=" in line:
            key = line.split("=", 1)[0].strip()

            # Check if this key needs to be updated
            updated = False
            for field_name, env_name in field_to_env.items():
                if key == env_name:
                    new_value = getattr(updates, field_name)
                    if new_value is not None:
                        # Don't update if it's a masked secret
                        if isinstance(new_value, str) and new_value.startswith("***"):
                            updated_lines.append(line)
                        else:
                            # Convert bool to string
                            if isinstance(new_value, bool):
                                new_value = str(new_value)
                            elif isinstance(new_value, int):
                                new_value = str(new_value)

                            updated_lines.append(f"{key}={new_value}")
                            updated_keys.add(key)
                        updated = True
                        break

            if not updated:
                updated_lines.append(line)
        else:
            updated_lines.append(line)

    # Write updated .env file
    env_path.write_text("\n".join(updated_lines) + "\n")

    # Return current settings (NOTE: Won't reflect changes until restart)
    return await get_settings()


def _mask_secret(value: Optional[str]) -> Optional[str]:
    """Mask secret values for API response"""
    if not value:
        return None

    if len(value) <= 8:
        return "***"

    return f"{value[:4]}***{value[-4:]}"

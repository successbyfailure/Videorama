"""
Videorama v2.0.0 - Settings API
Endpoints for managing application settings including LLM prompts
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from ...database import get_db
from ...models import Setting
from ...models.setting import DEFAULT_PROMPTS
from ...schemas.setting import SettingResponse, SettingUpdate, SettingCreate, SettingsCategory

router = APIRouter()


@router.get("/settings", response_model=List[SettingResponse])
def list_settings(
    category: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all settings, optionally filtered by category

    Args:
        category: Filter by category (llm, ui, system, etc.)
    """
    query = db.query(Setting)

    if category:
        query = query.filter(Setting.category == category)

    settings = query.all()

    # Initialize defaults if settings table is empty
    if not settings and not category:
        _initialize_default_settings(db)
        settings = db.query(Setting).all()

    return settings


@router.get("/settings/categories", response_model=List[SettingsCategory])
def list_settings_by_category(db: Session = Depends(get_db)):
    """
    List all settings grouped by category
    """
    # Get all unique categories
    categories = db.query(Setting.category).distinct().all()
    categories = [c[0] for c in categories if c[0]]

    # Initialize defaults if no settings exist
    if not categories:
        _initialize_default_settings(db)
        categories = db.query(Setting.category).distinct().all()
        categories = [c[0] for c in categories if c[0]]

    result = []
    for cat in categories:
        settings = db.query(Setting).filter(Setting.category == cat).all()
        result.append(SettingsCategory(
            category=cat,
            settings=settings
        ))

    return result


@router.get("/settings/{key}", response_model=SettingResponse)
def get_setting(key: str, db: Session = Depends(get_db)):
    """
    Get a specific setting by key
    """
    setting = db.query(Setting).filter(Setting.key == key).first()

    if not setting:
        # Try to initialize from defaults
        if key in DEFAULT_PROMPTS:
            setting = _create_default_setting(db, key)
        else:
            raise HTTPException(status_code=404, detail=f"Setting not found: {key}")

    return setting


@router.post("/settings", response_model=SettingResponse)
def create_setting(
    setting_data: SettingCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new setting
    """
    # Check if setting already exists
    existing = db.query(Setting).filter(Setting.key == setting_data.key).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"Setting already exists: {setting_data.key}")

    setting = Setting(**setting_data.model_dump())
    db.add(setting)
    db.commit()
    db.refresh(setting)

    return setting


@router.patch("/settings/{key}", response_model=SettingResponse)
def update_setting(
    key: str,
    setting_update: SettingUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a setting's value
    """
    setting = db.query(Setting).filter(Setting.key == key).first()

    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting not found: {key}")

    setting.value = setting_update.value
    db.commit()
    db.refresh(setting)

    return setting


@router.delete("/settings/{key}")
def delete_setting(key: str, db: Session = Depends(get_db)):
    """
    Delete a setting
    """
    setting = db.query(Setting).filter(Setting.key == key).first()

    if not setting:
        raise HTTPException(status_code=404, detail=f"Setting not found: {key}")

    db.delete(setting)
    db.commit()

    return {"message": f"Setting deleted: {key}"}


@router.post("/settings/{key}/reset", response_model=SettingResponse)
def reset_setting_to_default(key: str, db: Session = Depends(get_db)):
    """
    Reset a setting to its default value
    """
    if key not in DEFAULT_PROMPTS:
        raise HTTPException(status_code=400, detail=f"No default value for setting: {key}")

    setting = db.query(Setting).filter(Setting.key == key).first()

    if not setting:
        # Create from default
        setting = _create_default_setting(db, key)
    else:
        # Update to default
        default_data = DEFAULT_PROMPTS[key]
        setting.value = default_data["value"]
        db.commit()
        db.refresh(setting)

    return setting


def _initialize_default_settings(db: Session):
    """Initialize database with default settings"""
    for key, data in DEFAULT_PROMPTS.items():
        existing = db.query(Setting).filter(Setting.key == key).first()
        if not existing:
            setting = Setting(
                key=key,
                value=data["value"],
                category=data["category"],
                description=data["description"],
            )
            db.add(setting)

    db.commit()


def _create_default_setting(db: Session, key: str) -> Setting:
    """Create a setting from default"""
    if key not in DEFAULT_PROMPTS:
        raise HTTPException(status_code=404, detail=f"No default for setting: {key}")

    data = DEFAULT_PROMPTS[key]
    setting = Setting(
        key=key,
        value=data["value"],
        category=data["category"],
        description=data["description"],
    )
    db.add(setting)
    db.commit()
    db.refresh(setting)

    return setting

"""
Videorama v2.0.0 - Setting Schemas
Pydantic schemas for settings API
"""

from pydantic import BaseModel, Field
from typing import Optional


class SettingBase(BaseModel):
    """Base setting schema"""
    key: str = Field(..., description="Unique setting key")
    value: str = Field(..., description="Setting value (can be JSON, text, etc.)")
    category: Optional[str] = Field(None, description="Setting category (llm, ui, system, etc.)")
    description: Optional[str] = Field(None, description="Human-readable description")
    is_secret: bool = Field(False, description="Whether to hide value in UI")


class SettingCreate(SettingBase):
    """Schema for creating a new setting"""
    pass


class SettingUpdate(BaseModel):
    """Schema for updating a setting (only value can be updated)"""
    value: str = Field(..., description="New setting value")


class SettingResponse(SettingBase):
    """Schema for setting responses"""

    class Config:
        from_attributes = True


class SettingsCategory(BaseModel):
    """Schema for grouped settings by category"""
    category: str
    settings: list[SettingResponse]

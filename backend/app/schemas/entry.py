"""
Videorama v2.0.0 - Entry Schemas
Pydantic models for entry validation
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime


class EntryFileBase(BaseModel):
    """Base schema for entry files"""

    file_type: str = Field(..., pattern="^(video|audio|thumbnail|subtitle)$")
    format: Optional[str] = None
    size: Optional[int] = Field(None, ge=0)
    duration: Optional[int] = Field(None, ge=0)
    bitrate: Optional[int] = Field(None, ge=0)
    resolution: Optional[str] = None


class EntryFileResponse(EntryFileBase):
    """Response schema for entry files"""

    id: str
    entry_uuid: str
    file_path: str
    content_hash: str
    is_available: bool = True
    last_verified_at: Optional[float] = None
    created_at: Optional[float] = None

    class Config:
        from_attributes = True


class EntryPropertyResponse(BaseModel):
    """Response schema for entry properties with source tracking"""

    key: str
    value: str
    source: Optional[str] = None  # 'llm', 'api:itunes', 'api:tmdb', 'user', etc.

    class Config:
        from_attributes = True


class EntryBase(BaseModel):
    """Base schema for entries"""

    title: str = Field(..., min_length=1, max_length=500)
    description: Optional[str] = None
    duration: Optional[int] = Field(None, ge=0)
    thumbnail_url: Optional[str] = None
    library_id: str
    subfolder: Optional[str] = None
    platform: Optional[str] = None
    uploader: Optional[str] = None
    import_source: Optional[str] = Field(
        None, pattern="^(web|browser-plugin|telegram-bot|mcp|filesystem)$"
    )


class EntryCreate(EntryBase):
    """Schema for creating an entry"""

    original_url: Optional[str] = None
    imported_by: Optional[str] = None
    properties: Dict[str, str] = Field(default_factory=dict)
    tags: List[str] = Field(default_factory=list)  # User tags


class EntryUpdate(BaseModel):
    """Schema for updating an entry (all fields optional)"""

    title: Optional[str] = Field(None, min_length=1, max_length=500)
    description: Optional[str] = None
    duration: Optional[int] = Field(None, ge=0)
    thumbnail_url: Optional[str] = None
    subfolder: Optional[str] = None
    favorite: Optional[bool] = None
    rating: Optional[int] = Field(None, ge=1, le=5)


class EntryResponse(EntryBase):
    """Schema for entry response"""

    uuid: str
    original_url: Optional[str] = None
    imported_by: Optional[str] = None
    view_count: int = 0
    favorite: bool = False
    rating: Optional[int] = None
    added_at: float
    updated_at: Optional[float] = None
    last_viewed_at: Optional[float] = None
    import_job_id: Optional[str] = None

    # Related data (populated separately)
    files: List[EntryFileResponse] = Field(default_factory=list)
    properties: List[EntryPropertyResponse] = Field(default_factory=list)  # Changed to list with source
    auto_tags: List[str] = Field(default_factory=list)
    user_tags: List[str] = Field(default_factory=list)
    relations: List[Dict] = Field(default_factory=list)

    class Config:
        from_attributes = True

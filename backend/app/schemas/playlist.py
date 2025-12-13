"""
Videorama v2.0.0 - Playlist Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict


class PlaylistBase(BaseModel):
    """Base playlist schema"""

    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    library_id: Optional[str] = None
    is_dynamic: bool = False
    query: Optional[Dict] = None  # JSON query for dynamic playlists
    sort_by: Optional[str] = "added_at"
    sort_order: Optional[str] = Field(default="desc", pattern="^(asc|desc)$")
    limit_results: Optional[int] = Field(None, ge=1)


class PlaylistCreate(PlaylistBase):
    """Schema for creating a playlist"""

    pass


class PlaylistUpdate(BaseModel):
    """Schema for updating a playlist"""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    query: Optional[Dict] = None
    sort_by: Optional[str] = None
    sort_order: Optional[str] = Field(None, pattern="^(asc|desc)$")
    limit_results: Optional[int] = Field(None, ge=1)


class PlaylistResponse(PlaylistBase):
    """Schema for playlist response"""

    id: str
    created_at: float
    updated_at: Optional[float] = None
    entry_count: int = 0  # Computed field

    class Config:
        from_attributes = True

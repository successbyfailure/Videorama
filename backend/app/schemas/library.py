"""
Videorama v2.0.0 - Library Schemas
Pydantic models for library validation
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class LibraryBase(BaseModel):
    """Base library schema"""

    name: str = Field(..., min_length=1, max_length=100)
    icon: str = Field(default="📁", max_length=10)
    default_path: str = Field(..., min_length=1)
    additional_paths: List[str] = Field(default_factory=list)
    auto_organize: bool = Field(default=True)
    path_template: Optional[str] = None
    auto_tag_from_path: bool = Field(default=False)
    is_private: bool = Field(default=False)
    llm_confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    watch_folders: List[Dict] = Field(default_factory=list)
    scan_interval: int = Field(default=1800, ge=60)
    external_sources: Dict[str, bool] = Field(default_factory=dict)


class LibraryCreate(LibraryBase):
    """Schema for creating a library"""

    id: str = Field(..., min_length=1, max_length=50, pattern="^[a-z0-9_-]+$")


class LibraryUpdate(BaseModel):
    """Schema for updating a library (all fields optional)"""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    icon: Optional[str] = Field(None, max_length=10)
    default_path: Optional[str] = None
    additional_paths: Optional[List[str]] = None
    auto_organize: Optional[bool] = None
    path_template: Optional[str] = None
    auto_tag_from_path: Optional[bool] = None
    is_private: Optional[bool] = None
    llm_confidence_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    watch_folders: Optional[List[Dict]] = None
    scan_interval: Optional[int] = Field(None, ge=60)
    external_sources: Optional[Dict[str, bool]] = None


class LibraryResponse(LibraryBase):
    """Schema for library response"""

    id: str
    last_scan_at: Optional[float] = None

    class Config:
        from_attributes = True  # For SQLAlchemy models

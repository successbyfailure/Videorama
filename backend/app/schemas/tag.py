"""
Videorama v2.0.0 - Tag Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, List


class TagBase(BaseModel):
    """Base tag schema"""

    name: str = Field(..., min_length=1, max_length=100)
    parent_id: Optional[int] = None


class TagCreate(TagBase):
    """Schema for creating a tag"""

    pass


class TagResponse(TagBase):
    """Schema for tag response"""

    id: int
    children: List["TagResponse"] = Field(default_factory=list)

    class Config:
        from_attributes = True


# For recursive model
TagResponse.model_rebuild()

"""
Videorama v2.0.0 - Inbox Schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict
import json


class InboxItemResponse(BaseModel):
    """Schema for inbox item response"""

    id: str
    job_id: Optional[str] = None
    type: str = Field(..., pattern="^(duplicate|low_confidence|failed|needs_review)$")
    entry_data: Dict  # Temporary entry data
    suggested_library: Optional[str] = None
    suggested_metadata: Optional[Dict] = None
    confidence: Optional[float] = None
    error_message: Optional[str] = None
    reviewed: bool = False
    created_at: float

    @field_validator('entry_data', mode='before')
    @classmethod
    def parse_entry_data(cls, v):
        """Parse entry_data from JSON string if needed"""
        if v is None:
            return {}
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return {}
        return v

    @field_validator('suggested_metadata', mode='before')
    @classmethod
    def parse_suggested_metadata(cls, v):
        """Parse suggested_metadata from JSON string if needed"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return None
        return v

    class Config:
        from_attributes = True

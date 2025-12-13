"""
Videorama v2.0.0 - Inbox Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict


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

    class Config:
        from_attributes = True

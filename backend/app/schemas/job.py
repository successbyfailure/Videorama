"""
Videorama v2.0.0 - Job Schemas
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict


class JobCreate(BaseModel):
    """Schema for creating a job"""

    type: str = Field(
        ...,
        pattern="^(import|import_filesystem|move|enrich|reindex)$",
    )
    metadata: Optional[Dict] = None


class JobResponse(BaseModel):
    """Schema for job response"""

    id: str
    type: str
    status: str = Field(..., pattern="^(pending|running|completed|failed)$")
    progress: float = Field(0.0, ge=0.0, le=1.0)
    current_step: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    created_at: float
    started_at: Optional[float] = None
    updated_at: Optional[float] = None
    completed_at: Optional[float] = None

    class Config:
        from_attributes = True

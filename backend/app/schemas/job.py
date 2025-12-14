"""
Videorama v2.0.0 - Job Schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict
import json


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
    status: str = Field(..., pattern="^(pending|running|completed|failed|cancelled)$")
    progress: float = Field(0.0, ge=0.0, le=1.0)
    current_step: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    created_at: float
    started_at: Optional[float] = None
    updated_at: Optional[float] = None
    completed_at: Optional[float] = None

    @field_validator('result', mode='before')
    @classmethod
    def parse_result(cls, v):
        """Parse result from JSON string if needed"""
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

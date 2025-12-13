"""
Videorama v2.0.0 - Jobs API
Monitor async job progress
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from ...database import get_db
from ...models.job import Job
from ...schemas.job import JobResponse
from ...services.job_service import JobService

router = APIRouter()


@router.get("/jobs", response_model=List[JobResponse])
def list_jobs(
    job_type: Optional[str] = Query(None, description="Filter by type"),
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """List jobs with optional filters"""
    jobs = JobService.list_jobs(db, job_type=job_type, status=status, limit=limit)
    return jobs


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get job status and progress"""
    job = JobService.get_job(db, job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return job


@router.delete("/jobs/cleanup")
def cleanup_old_jobs(
    max_age_hours: int = Query(24, ge=1, le=168, description="Max age in hours"),
    db: Session = Depends(get_db),
):
    """Clean up old completed/failed jobs"""
    count = JobService.cleanup_old_jobs(db, max_age_seconds=max_age_hours * 3600)

    return {"deleted": count, "message": f"Deleted {count} old jobs"}

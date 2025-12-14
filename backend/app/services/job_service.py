"""
Videorama v2.0.0 - Job Service
Persistent job management for async operations
"""

from sqlalchemy.orm import Session
from typing import Optional, Dict, Any
import time
import uuid
import json

from ..models.job import Job
from ..schemas.job import JobCreate


class JobService:
    """Service for managing persistent jobs"""

    @staticmethod
    def create_job(db: Session, job_create: JobCreate) -> Job:
        """
        Create a new job

        Args:
            db: Database session
            job_create: Job creation data

        Returns:
            Created job
        """
        job = Job(
            id=str(uuid.uuid4()),
            type=job_create.type,
            status="pending",
            progress=0.0,
            created_at=time.time(),
        )

        db.add(job)
        db.commit()
        db.refresh(job)

        return job

    @staticmethod
    def get_job(db: Session, job_id: str) -> Optional[Job]:
        """
        Get a job by ID

        Args:
            db: Database session
            job_id: Job ID

        Returns:
            Job or None if not found
        """
        return db.query(Job).filter(Job.id == job_id).first()

    @staticmethod
    def update_job_status(
        db: Session,
        job_id: str,
        status: str,
        progress: Optional[float] = None,
        current_step: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Optional[Job]:
        """
        Update job status

        Args:
            db: Database session
            job_id: Job ID
            status: New status
            progress: Progress (0.0 to 1.0)
            current_step: Description of current step
            error: Error message if failed

        Returns:
            Updated job or None
        """
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            return None

        job.status = status
        job.updated_at = time.time()

        if progress is not None:
            job.progress = progress

        if current_step is not None:
            job.current_step = current_step

        if error is not None:
            job.error = error

        # Set started_at if moving to running
        if status == "running" and not job.started_at:
            job.started_at = time.time()

        # Set completed_at if completed or failed
        if status in ["completed", "failed"] and not job.completed_at:
            job.completed_at = time.time()

        db.commit()
        db.refresh(job)

        return job

    @staticmethod
    def set_job_result(
        db: Session, job_id: str, result: Dict[str, Any]
    ) -> Optional[Job]:
        """
        Set job result data

        Args:
            db: Database session
            job_id: Job ID
            result: Result data

        Returns:
            Updated job or None
        """
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            return None

        job.result = json.dumps(result)
        job.updated_at = time.time()

        db.commit()
        db.refresh(job)

        return job

    @staticmethod
    def list_jobs(
        db: Session,
        job_type: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> list[Job]:
        """
        List jobs with optional filters

        Args:
            db: Database session
            job_type: Filter by job type
            status: Filter by status
            limit: Maximum number of jobs to return

        Returns:
            List of jobs
        """
        query = db.query(Job)

        if job_type:
            query = query.filter(Job.type == job_type)

        if status:
            query = query.filter(Job.status == status)

        return query.order_by(Job.created_at.desc()).limit(limit).all()

    @staticmethod
    def cleanup_old_jobs(db: Session, max_age_seconds: int = 86400) -> int:
        """
        Clean up old completed/failed jobs

        Args:
            db: Database session
            max_age_seconds: Maximum age in seconds (default: 24h)

        Returns:
            Number of jobs deleted
        """
        cutoff_time = time.time() - max_age_seconds

        count = (
            db.query(Job)
            .filter(
                Job.status.in_(["completed", "failed", "cancelled"]),
                Job.completed_at < cutoff_time,
            )
            .delete()
        )

        db.commit()

        return count

    @staticmethod
    def cancel_job(db: Session, job_id: str) -> Optional[Job]:
        """
        Cancel a running job

        Args:
            db: Database session
            job_id: Job ID to cancel

        Returns:
            Updated job or None if not found
        """
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            return None

        # Only cancel if job is pending or running
        if job.status not in ["pending", "running"]:
            return job

        # Update status to cancelled
        job.status = "cancelled"
        job.updated_at = time.time()
        job.completed_at = time.time()

        db.commit()
        db.refresh(job)

        # Try to revoke Celery task if it exists
        try:
            from ..tasks import celery_app
            celery_app.control.revoke(job_id, terminate=True)
        except Exception:
            # Ignore errors if Celery is not available or task doesn't exist
            pass

        return job

    @staticmethod
    def delete_job(db: Session, job_id: str) -> bool:
        """
        Delete a job from the database

        Args:
            db: Database session
            job_id: Job ID to delete

        Returns:
            True if deleted, False if not found
        """
        job = db.query(Job).filter(Job.id == job_id).first()

        if not job:
            return False

        db.delete(job)
        db.commit()

        return True

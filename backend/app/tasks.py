"""
Videorama v2.0.0 - Celery Tasks
Background tasks for asynchronous processing
"""

from celery import Celery
from .config import settings

# Initialize Celery
celery_app = Celery(
    "videorama",
    broker=settings.CELERY_BROKER_URL if hasattr(settings, 'CELERY_BROKER_URL') else "redis://redis:6379/0",
    backend=settings.CELERY_RESULT_BACKEND if hasattr(settings, 'CELERY_RESULT_BACKEND') else "redis://redis:6379/0"
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    beat_schedule={
        'cleanup-old-jobs': {
            'task': 'app.tasks.cleanup_old_jobs_task',
            'schedule': 86400.0,  # Run daily (every 24 hours)
        },
    },
)


@celery_app.task(name="app.tasks.test_task")
def test_task(message: str) -> dict:
    """
    Test task to verify Celery is working

    Args:
        message: A test message

    Returns:
        dict: Task result
    """
    return {"status": "success", "message": f"Received: {message}"}


@celery_app.task(name="app.tasks.import_from_url_task")
def import_from_url_task(
    job_id: str,
    url: str,
    library_id: str = None,
    user_metadata: dict = None,
    imported_by: str = None,
    auto_mode: bool = True,
    media_format: str = None,
) -> dict:
    """
    Async task to import media from URL

    Args:
        job_id: Job ID to track progress
        url: Source URL
        library_id: Target library (None = auto-detect)
        user_metadata: User-provided metadata override
        imported_by: User who triggered import
        auto_mode: Auto-import if confidence high, else inbox
        media_format: VHS format (video_max, audio_max, etc.)

    Returns:
        dict: Import result with entry_uuid or inbox_id
    """
    from .database import SessionLocal
    from .services.import_service import ImportService

    db = SessionLocal()
    try:
        import asyncio
        import_service = ImportService(db)

        # Create event loop and run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                import_service.import_from_url(
                    url=url,
                    library_id=library_id,
                    user_metadata=user_metadata,
                    imported_by=imported_by,
                    auto_mode=auto_mode,
                    media_format=media_format,
                    job_id=job_id  # Pass existing job_id
                )
            )
            return result
        finally:
            loop.close()
    finally:
        db.close()


@celery_app.task(name="app.tasks.cleanup_old_jobs_task")
def cleanup_old_jobs_task() -> dict:
    """
    Periodic task to clean up old completed/failed/cancelled jobs
    Runs daily and deletes jobs older than 10 days

    Returns:
        dict: Cleanup result with count
    """
    from .database import SessionLocal
    from .services.job_service import JobService

    db = SessionLocal()
    try:
        # Delete jobs older than 10 days
        count = JobService.cleanup_old_jobs(db, max_age_seconds=10 * 24 * 3600)
        return {"status": "success", "deleted": count, "message": f"Cleaned up {count} old jobs"}
    finally:
        db.close()

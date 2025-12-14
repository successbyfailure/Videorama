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

@celery_app.task(name="app.tasks.reindex_library_task")
def reindex_library_task(job_id: str, library_id: str) -> dict:
    """
    Reindex job: walk the library path, verify indexed files, and enqueue missing files to inbox.
    """
    from .database import SessionLocal
    from .services.job_service import JobService
    from .models.library import Library
    from .models import EntryFile, InboxItem
    from .utils.hash import calculate_file_hash
    from pathlib import Path
    import os
    import json
    import time

    db = SessionLocal()
    try:
        job_service = JobService()
        job_service.update_job_status(db, job_id, "running", 0.1, "Scanning library path")

        library = db.query(Library).filter(Library.id == library_id).first()
        if not library:
            job_service.update_job_status(db, job_id, "failed", error="Library not found")
            return {"status": "error", "message": "Library not found"}

        root = Path(library.default_path)
        scanned = 0
        sent_to_inbox = 0
        allowed_exts = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".mp3", ".m4a", ".flac", ".wav", ".ogg"}

        for dirpath, _, files in os.walk(root):
            for fname in files:
                scanned += 1
                path = Path(dirpath) / fname
                if path.suffix.lower() not in allowed_exts:
                    continue

                try:
                    content_hash = calculate_file_hash(path)
                except Exception:
                    continue

                existing = db.query(EntryFile).filter(EntryFile.content_hash == content_hash).first()
                if existing:
                    continue

                # Not indexed -> send to inbox for manual classification
                rel_subfolder = ""
                try:
                    rel_subfolder = str(path.parent.relative_to(root))
                except Exception:
                    rel_subfolder = ""

                entry_data = {
                    "title": path.stem,
                    "original_url": None,
                    "metadata": {"filename": fname, "file_path": str(path), "size": path.stat().st_size},
                    "enriched": {},
                    "file_path": str(path),
                    "content_hash": content_hash,
                }
                inbox_item = InboxItem(
                    job_id=job_id,
                    type="needs_review",
                    entry_data=json.dumps(entry_data),
                    suggested_library=library_id,
                    suggested_metadata=json.dumps({"library": library_id, "subfolder": rel_subfolder}),
                    confidence=0.0,
                    error_message=None,
                    reviewed=False,
                    created_at=time.time(),
                )
                db.add(inbox_item)
                sent_to_inbox += 1

        db.commit()
        job_service.update_job_status(db, job_id, "completed", 1.0, "Reindex completed")
        job_service.set_job_result(db, job_id, {"files_found": scanned, "sent_to_inbox": sent_to_inbox})
        return {"status": "success", "files_found": scanned, "sent_to_inbox": sent_to_inbox}
    except Exception as e:
        job_service.update_job_status(db, job_id, "failed", error=str(e))
        return {"status": "error", "message": str(e)}
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

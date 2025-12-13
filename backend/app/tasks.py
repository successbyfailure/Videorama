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


# Add more tasks here as needed
# Example:
# @celery_app.task(name="app.tasks.process_video")
# def process_video(video_id: int) -> dict:
#     """Process a video file"""
#     pass

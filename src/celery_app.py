"""
Celery application configuration for UGA Course Scheduler.

Provides async task processing for:
- Schedule scanning (scanning web interface for course data)
- Seat availability updates
- RAG pipeline processing
- Embedding generation
- Seat alerts
"""
from celery import Celery
from celery.schedules import crontab

from src.config import settings

# Create Celery app
celery_app = Celery(
    "uga_scheduler",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "src.tasks.scanner_tasks",
        "src.tasks.embedding_tasks",
    ],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="America/New_York",  # UGA timezone
    enable_utc=True,

    # Task execution settings
    task_acks_late=True,  # Acknowledge after completion for reliability
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # One task at a time for memory efficiency

    # Result settings
    result_expires=3600,  # Results expire after 1 hour

    # Beat scheduler (for periodic tasks)
    beat_schedule={
        # Seat availability updates - every 15 minutes during business hours
        "update-seat-availability": {
            "task": "src.tasks.scanner_tasks.update_all_seat_availability",
            "schedule": 900.0,  # Every 15 minutes
        },
        # Check seat alerts - every 5 minutes for timely notifications
        "check-seat-alerts": {
            "task": "src.tasks.embedding_tasks.check_seat_alerts_task",
            "schedule": 300.0,  # Every 5 minutes
        },
        # Track seat changes for analytics - every hour
        "track-seat-changes": {
            "task": "src.tasks.embedding_tasks.track_seat_changes_task",
            "schedule": 3600.0,  # Every hour
        },
        # Daily embedding of new content - once per day at 3 AM ET
        "daily-embedding": {
            "task": "src.tasks.embedding_tasks.embed_all_content",
            "schedule": crontab(hour=3, minute=0),
        },
    },
)


def get_celery_app() -> Celery:
    """Get the Celery application instance."""
    return celery_app

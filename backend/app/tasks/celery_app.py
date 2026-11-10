"""Celery tasks for background processing."""
from celery import Celery
from app.config import settings

celery_app = Celery(
    "road_safety",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "refresh-traffic-every-5-min": {
            "task": "app.tasks.traffic_tasks.refresh_traffic_snapshot",
            "schedule": 300,  # every 5 minutes
        },
        "compute-hotspots-every-hour": {
            "task": "app.tasks.traffic_tasks.compute_hotspots",
            "schedule": 3600,
        },
    }
)

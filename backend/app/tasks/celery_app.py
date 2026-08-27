from celery import Celery

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings, service="flowtracer-worker")

celery_app = Celery(
    "flowtracer",
    broker=settings.celery_broker_url.get_secret_value(),
    backend=settings.celery_result_backend.get_secret_value(),
    include=["app.tasks.health", "app.tasks.acquisition", "app.tasks.intelligence"],
)
celery_app.conf.update(
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
    worker_redirect_stdouts=False,
    beat_schedule={
        "schedule-due-sources": {
            "task": "flowtracer.tasks.acquisition.schedule_due_sources",
            "schedule": 60.0,
        },
        "dispatch-queued-runs": {
            "task": "flowtracer.tasks.acquisition.dispatch_queued_runs",
            "schedule": 60.0,
        },
        "dispatch-fetched-raw-items": {
            "task": "flowtracer.tasks.intelligence.dispatch_fetched_raw_items",
            "schedule": 60.0,
        },
        "dispatch-pending-analyses": {
            "task": "flowtracer.tasks.intelligence.dispatch_pending_analyses",
            "schedule": 60.0,
        },
        "recover-stale-analyses": {
            "task": "flowtracer.tasks.intelligence.recover_stale_analyses",
            "schedule": 60.0,
        },
    },
)

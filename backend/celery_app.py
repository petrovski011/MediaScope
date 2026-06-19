from celery import Celery
from celery.schedules import crontab

from config import settings

celery = Celery(
    "mediascope",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=["pipeline.tasks"],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Belgrade",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)

celery.conf.beat_schedule = {
    # Nocni batch: prethodni dan, svi clanci u jednom batch-u (do 3000)
    "nightly-analysis-batch": {
        "task": "pipeline.tasks.submit_nightly_batch",
        "schedule": crontab(hour=22, minute=30),
    },
    # Catch-up: dok god ima backlog-a, submituj sledeci batch svaki sat
    "catchup-analysis-batch": {
        "task": "pipeline.tasks.submit_catchup_batches",
        "schedule": crontab(minute=0),  # svaki sat, na punom satu
    },
    # Proveravaj status batch-a svakih 15 minuta
    "check-batch-results": {
        "task": "pipeline.tasks.check_and_process_batch",
        "schedule": crontab(minute="*/15"),
    },
    # Jutarnji pregled u 07:00
    "morning-summary": {
        "task": "pipeline.tasks.generate_morning_summary",
        "schedule": crontab(hour=7, minute=0),
    },
    # Narativno poklapanje jednom dnevno u 06:00
    "narrative-matching": {
        "task": "pipeline.tasks.compute_narrative_matching",
        "schedule": crontab(hour=6, minute=0),
    },
}

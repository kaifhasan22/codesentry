from celery import Celery

from app.config import get_settings

settings = get_settings()
celery_app = Celery("codesentry", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=270,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)

celery_app.conf.imports = ("app.tasks.scan",)

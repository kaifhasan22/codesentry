from celery import Celery

from app.config import get_settings

settings = get_settings()
celery_app = Celery("codesentry", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(
    task_track_started=True,
    task_default_queue=settings.worker_queue,
    task_time_limit=300,
    task_soft_time_limit=270,
    task_acks_late=True,
    task_reject_on_worker_lost=False,
    task_acks_on_failure_or_timeout=True,
    accept_content=["json"],
    task_serializer="json",
    result_serializer="json",
    task_ignore_result=True,
    broker_connection_timeout=5,
    task_publish_retry=False,
    worker_max_tasks_per_child=20,
    worker_prefetch_multiplier=1,
)

celery_app.conf.imports = ("app.tasks.scan",)

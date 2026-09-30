import ssl

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

# Hosted Redis URLs use TLS. Plain redis:// keeps the local Compose settings.
if settings.redis_url.startswith("rediss://"):
    tls = {"ssl_cert_reqs": ssl.CERT_REQUIRED, "ssl_check_hostname": True}
    celery_app.conf.update(broker_use_ssl=tls, redis_backend_use_ssl=tls.copy())

celery_app.conf.imports = ("app.tasks.scan",)

from celery import Celery

from tax_copilot.core.config import settings

celery_app = Celery(
    "tax_copilot",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_time_limit=120,
    task_soft_time_limit=90,
    worker_prefetch_multiplier=1,
)

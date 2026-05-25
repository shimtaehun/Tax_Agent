"""Celery 앱 설정.

브로커(메시지 큐)와 결과 백엔드 모두 Redis를 사용한다.
"""

from celery import Celery

from tax_copilot.core.config import settings

celery_app = Celery(
    "tax_copilot",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["tax_copilot.workers.tasks.receipts"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Seoul",
    enable_utc=True,
    # acks_late: 태스크가 완료된 후에야 메시지를 ACK한다.
    # worker가 SIGKILL을 받으면 메시지가 재큐잉되어 다른 worker가 처리한다.
    task_acks_late=True,
    # worker가 예기치 않게 종료되면 태스크를 재큐잉한다.
    task_reject_on_worker_lost=True,
    # acks_late와 함께 사용할 때 하나의 worker가 하나의 태스크만 처리하도록 강제한다.
    worker_prefetch_multiplier=1,
)

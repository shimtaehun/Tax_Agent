"""Redis 분산 락.

SET key value NX EX seconds 명령을 사용한다.
NX: Not eXists일 때만 세팅 (다른 프로세스가 먼저 잡으면 실패)
EX: 만료 시간 (worker 장애로 락이 영원히 잠기는 상황을 방지)
"""

import redis

from tax_copilot.core.config import settings


def _get_client() -> redis.Redis:
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def acquire_lock(key: str, ttl_seconds: int = 300) -> bool:
    """Redis NX 락을 획득한다. 성공 시 True, 이미 잠겨 있으면 False."""
    client = _get_client()
    result = client.set(key, "1", nx=True, ex=ttl_seconds)
    return result is not None


def release_lock(key: str) -> None:
    """Redis 락을 해제한다."""
    client = _get_client()
    client.delete(key)

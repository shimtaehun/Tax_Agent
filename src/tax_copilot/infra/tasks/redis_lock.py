from typing import Any


class RedisReceiptLock:
    def __init__(self, redis_client: Any) -> None:
        self._redis_client = redis_client

    def acquire(self, key: str, ttl_seconds: int) -> bool:
        result = self._redis_client.set(key, "1", nx=True, ex=ttl_seconds)
        return bool(result)

    def release(self, key: str) -> None:
        self._redis_client.delete(key)

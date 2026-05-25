"""Phase 5 Celery + Redis 분산 락 테스트.

실제 Redis와 Celery worker 없이 fakeredis와 unittest.mock으로 검증한다.
테스트 목표:
1. Redis 락 단위 테스트 (acquire/release)
2. dispatch_receipt_task: 락 획득 + 태스크 큐잉
3. dispatch_receipt_task: 이중 호출 시 DuplicateReceiptError
4. _process_async: 이미 완료된 영수증은 재처리하지 않음 (idempotency)
5. _process_async: PROCESSING 상태 설정 후 워크플로우 실행
"""

from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis
import pytest

from tax_copilot.core.exceptions import DuplicateReceiptError

# ─── Redis 락 단위 테스트 ──────────────────────────────────────────────────


class TestRedisLock:
    """infra/cache/redis_lock.py 단위 테스트. fakeredis로 실제 Redis 대체."""

    @pytest.fixture(autouse=True)
    def patch_redis(self):
        """redis.Redis.from_url을 fakeredis로 교체한다."""
        fake = fakeredis.FakeRedis(decode_responses=True)
        with patch("tax_copilot.infra.cache.redis_lock._get_client", return_value=fake):
            self.fake_redis = fake
            yield

    def test_acquire_lock_succeeds_when_free(self) -> None:
        """비어 있는 키에 락을 획득하면 True를 반환한다."""
        from tax_copilot.infra.cache.redis_lock import acquire_lock

        result = acquire_lock("test:key", ttl_seconds=60)
        assert result is True

    def test_acquire_lock_fails_when_held(self) -> None:
        """다른 프로세스가 이미 락을 보유 중이면 False를 반환한다."""
        from tax_copilot.infra.cache.redis_lock import acquire_lock

        acquire_lock("test:key", ttl_seconds=60)  # 첫 번째 획득
        result = acquire_lock("test:key", ttl_seconds=60)  # 두 번째 시도
        assert result is False

    def test_release_lock_allows_reacquire(self) -> None:
        """락을 해제하면 다시 획득할 수 있다."""
        from tax_copilot.infra.cache.redis_lock import acquire_lock, release_lock

        acquire_lock("test:key", ttl_seconds=60)
        release_lock("test:key")
        result = acquire_lock("test:key", ttl_seconds=60)
        assert result is True

    def test_lock_key_has_ttl(self) -> None:
        """NX EX로 설정된 키에 TTL이 존재한다."""
        from tax_copilot.infra.cache.redis_lock import acquire_lock

        acquire_lock("test:key", ttl_seconds=120)
        ttl = self.fake_redis.ttl("test:key")
        assert 0 < ttl <= 120

    def test_different_keys_are_independent(self) -> None:
        """서로 다른 키는 독립적으로 동작한다."""
        from tax_copilot.infra.cache.redis_lock import acquire_lock

        assert acquire_lock("key:A") is True
        assert acquire_lock("key:B") is True  # A가 잠겨 있어도 B는 획득 가능


# ─── dispatch_receipt_task 단위 테스트 ────────────────────────────────────


class TestDispatchReceiptTask:
    """dispatch_receipt_task: 락 + Celery 큐잉 동작 검증."""

    @pytest.fixture(autouse=True)
    def patch_redis(self):
        fake = fakeredis.FakeRedis(decode_responses=True)
        with patch("tax_copilot.infra.cache.redis_lock._get_client", return_value=fake):
            yield

    def test_dispatch_returns_task_id(self) -> None:
        """dispatch_receipt_task가 Celery task ID 문자열을 반환한다."""
        from tax_copilot.workers.tasks.receipts import dispatch_receipt_task

        mock_task = MagicMock()
        mock_task.id = "celery-task-abc123"
        with patch(
            "tax_copilot.workers.tasks.receipts.process_receipt_task.apply_async",
            return_value=mock_task,
        ):
            task_id = dispatch_receipt_task(
                tenant_id=1,
                receipt_id=10,
                file_path="/tmp/test.jpg",  # noqa: S108
                file_hash="deadbeef" * 8,
            )
        assert task_id == "celery-task-abc123"

    def test_dispatch_sets_redis_lock(self) -> None:
        """dispatch 호출 후 Redis에 락 키가 존재한다."""
        from tax_copilot.infra.cache.redis_lock import _get_client
        from tax_copilot.workers.tasks.receipts import dispatch_receipt_task

        file_hash = "aabbccdd" * 8
        mock_task = MagicMock()
        mock_task.id = "task-xyz"
        with patch(
            "tax_copilot.workers.tasks.receipts.process_receipt_task.apply_async",
            return_value=mock_task,
        ):
            dispatch_receipt_task(
                tenant_id=2,
                receipt_id=20,
                file_path="/tmp/x.jpg",  # noqa: S108
                file_hash=file_hash,
            )

        client = _get_client()
        assert client.exists(f"lock:receipt:2:{file_hash}") == 1

    def test_dispatch_duplicate_raises_error(self) -> None:
        """동일 파일에 두 번 dispatch하면 DuplicateReceiptError가 발생한다."""
        from tax_copilot.workers.tasks.receipts import dispatch_receipt_task

        file_hash = "11223344" * 8
        mock_task = MagicMock()
        mock_task.id = "task-first"
        with patch(
            "tax_copilot.workers.tasks.receipts.process_receipt_task.apply_async",
            return_value=mock_task,
        ):
            dispatch_receipt_task(
                tenant_id=3,
                receipt_id=30,
                file_path="/tmp/y.jpg",  # noqa: S108
                file_hash=file_hash,
            )

        with pytest.raises(DuplicateReceiptError, match="이미 처리 중"):
            dispatch_receipt_task(
                tenant_id=3,
                receipt_id=30,
                file_path="/tmp/y.jpg",  # noqa: S108
                file_hash=file_hash,
            )

    def test_lock_released_on_celery_failure(self) -> None:
        """Celery 큐잉이 실패하면 Redis 락이 해제된다."""
        from tax_copilot.infra.cache.redis_lock import _get_client
        from tax_copilot.workers.tasks.receipts import dispatch_receipt_task

        file_hash = "ffeebbaa" * 8
        with patch(
            "tax_copilot.workers.tasks.receipts.process_receipt_task.apply_async",
            side_effect=RuntimeError("Redis down"),
        ):
            with pytest.raises(RuntimeError):
                dispatch_receipt_task(
                    tenant_id=4,
                    receipt_id=40,
                    file_path="/tmp/z.jpg",  # noqa: S108
                    file_hash=file_hash,
                )

        # 큐잉 실패 → 락도 해제되어야 다음 시도가 가능
        client = _get_client()
        assert client.exists(f"lock:receipt:4:{file_hash}") == 0

    def test_lock_key_format(self) -> None:
        """lock 키 형식이 'lock:receipt:{tenant_id}:{file_hash}'이다."""
        from tax_copilot.infra.cache.redis_lock import _get_client
        from tax_copilot.workers.tasks.receipts import dispatch_receipt_task

        tenant_id = 99
        file_hash = "cafebabe" * 8
        mock_task = MagicMock()
        mock_task.id = "task-format-test"
        with patch(
            "tax_copilot.workers.tasks.receipts.process_receipt_task.apply_async",
            return_value=mock_task,
        ):
            dispatch_receipt_task(
                tenant_id=tenant_id,
                receipt_id=99,
                file_path="/tmp/q.jpg",  # noqa: S108
                file_hash=file_hash,
            )

        client = _get_client()
        assert client.exists(f"lock:receipt:{tenant_id}:{file_hash}") == 1


# ─── _process_async 단위 테스트 ───────────────────────────────────────────


class TestProcessAsync:
    """_process_async: DB 상태 확인 + LangGraph 호출 + DB 업데이트 검증."""

    @pytest.fixture(autouse=True)
    def patch_release_lock(self):
        """release_lock이 Redis에 실제 연결하지 않도록 mock한다."""
        with patch("tax_copilot.workers.tasks.receipts.release_lock"):
            yield

    def _make_mock_receipt(self, status: str) -> MagicMock:
        receipt = MagicMock()
        receipt.id = 1
        receipt.status = status
        return receipt

    @pytest.mark.asyncio
    async def test_skips_approved_receipt(self) -> None:
        """이미 APPROVED인 영수증은 재처리 없이 'skipped'를 반환한다."""
        from tax_copilot.infra.db.models.receipt import STATUS_APPROVED
        from tax_copilot.workers.tasks.receipts import _process_async

        receipt = self._make_mock_receipt(STATUS_APPROVED)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = receipt

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "tax_copilot.workers.tasks.receipts.AsyncSessionLocal",
            return_value=mock_session,
        ):
            result = await _process_async(
                tenant_id=1,
                receipt_id=1,
                file_path="/tmp/t.jpg",  # noqa: S108
                file_hash="abc123",
                attempt_number=1,
            )

        assert result["status"] == "skipped"
        assert result["reason"] == STATUS_APPROVED

    @pytest.mark.asyncio
    async def test_skips_needs_review_receipt(self) -> None:
        """NEEDS_REVIEW 상태도 재처리하지 않는다."""
        from tax_copilot.infra.db.models.receipt import STATUS_NEEDS_REVIEW
        from tax_copilot.workers.tasks.receipts import _process_async

        receipt = self._make_mock_receipt(STATUS_NEEDS_REVIEW)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = receipt

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "tax_copilot.workers.tasks.receipts.AsyncSessionLocal",
            return_value=mock_session,
        ):
            result = await _process_async(
                tenant_id=1,
                receipt_id=1,
                file_path="/tmp/t.jpg",  # noqa: S108
                file_hash="abc123",
                attempt_number=1,
            )

        assert result["status"] == "skipped"

    @pytest.mark.asyncio
    async def test_returns_error_when_receipt_not_found(self) -> None:
        """DB에 영수증이 없으면 'error'를 반환한다 (예외 없음)."""
        from tax_copilot.workers.tasks.receipts import _process_async

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "tax_copilot.workers.tasks.receipts.AsyncSessionLocal",
            return_value=mock_session,
        ):
            result = await _process_async(
                tenant_id=1,
                receipt_id=999,
                file_path="/tmp/t.jpg",  # noqa: S108
                file_hash="abc",
                attempt_number=1,
            )

        assert result["status"] == "error"
        assert result["reason"] == "receipt_not_found"

    @pytest.mark.asyncio
    async def test_sets_processing_status_before_workflow(self) -> None:
        """워크플로우 실행 전에 DB 상태를 PROCESSING으로 업데이트한다."""
        from tax_copilot.infra.db.models.receipt import STATUS_PENDING, STATUS_PROCESSING
        from tax_copilot.workers.tasks.receipts import _process_async

        # PENDING 영수증
        receipt = self._make_mock_receipt(STATUS_PENDING)
        committed_status = []

        async def mock_commit():
            committed_status.append(receipt.status)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = receipt

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = mock_commit
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        # LangGraph는 빈 상태를 반환하도록 mock
        mock_graph = AsyncMock()
        mock_graph.ainvoke = AsyncMock(
            return_value={
                "final_decision": {"vat_creditable": True},
                "requires_human": False,
                "transaction_date": None,
            }
        )

        mock_checkpointer = AsyncMock()
        mock_checkpointer.__aenter__ = AsyncMock(return_value=mock_checkpointer)
        mock_checkpointer.__aexit__ = AsyncMock(return_value=None)
        mock_checkpointer.setup = AsyncMock()
        mock_postgres_saver = MagicMock()
        mock_postgres_saver.from_conn_string = MagicMock(return_value=mock_checkpointer)

        with (
            patch(
                "tax_copilot.workers.tasks.receipts.AsyncSessionLocal",
                return_value=mock_session,
            ),
            patch(
                "tax_copilot.workers.tasks.receipts.build_graph",
                return_value=mock_graph,
            ),
            patch.dict(
                "sys.modules",
                {
                    "langgraph.checkpoint.postgres": MagicMock(),
                    "langgraph.checkpoint.postgres.aio": MagicMock(
                        AsyncPostgresSaver=mock_postgres_saver
                    ),
                },
            ),
        ):
            await _process_async(
                tenant_id=1,
                receipt_id=1,
                file_path="/tmp/t.jpg",  # noqa: S108
                file_hash="abc",
                attempt_number=1,
            )

        # 첫 번째 commit은 PROCESSING 상태여야 한다
        assert STATUS_PROCESSING in committed_status

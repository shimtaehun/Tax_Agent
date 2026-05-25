# Phase 5 완료 보고서 — Celery 비동기 작업 + Redis 분산 락

완료일: 2026-05-24

## 목표

영수증 처리를 FastAPI 요청 사이클에서 분리하여 비동기로 실행한다.
- `celery[redis]>=5.3` 의존성 추가
- `infra/cache/redis_lock.py`: Redis NX 락으로 동시 처리 방지
- `workers/celery_app.py`: Celery 앱 설정 (`acks_late`, `reject_on_worker_lost`)
- `workers/tasks/receipts.py`: `process_receipt_task` + `dispatch_receipt_task`
- API 엔드포인트 업데이트: DB 커밋 후 Celery 태스크 디스패치

---

## 구현한 컴포넌트

### Redis 분산 락 (`src/tax_copilot/infra/cache/redis_lock.py`)

```
acquire_lock(key, ttl_seconds=300) → bool
release_lock(key) → None
```

Redis `SET key 1 NX EX 300` 명령을 사용한다. NX는 키가 없을 때만 세팅하는 원자적 조건부 연산. EX는 TTL(Time To Live) — worker 장애로 락이 영원히 잠기는 상황을 방지한다.

### Celery 앱 (`src/tax_copilot/workers/celery_app.py`)

핵심 설정 3가지:
- `task_acks_late=True`: 태스크 완료 후 ACK. worker가 SIGKILL을 받으면 재큐잉.
- `task_reject_on_worker_lost=True`: worker 예기치 않은 종료 시 재큐잉.
- `worker_prefetch_multiplier=1`: worker당 한 번에 한 태스크만 처리.

브로커와 결과 백엔드 모두 Redis를 사용한다.

### process_receipt_task (`src/tax_copilot/workers/tasks/receipts.py`)

Celery는 동기 환경이므로 `asyncio.run()`으로 async 로직을 실행한다.

idempotency 보장 체인:
1. DB 상태 체크: APPROVED/NEEDS_REVIEW/FAILED면 재처리 없이 반환
2. DB 상태를 PROCESSING으로 업데이트
3. LangGraph 워크플로우 실행
4. 결과를 DB에 저장 (APPROVED/NEEDS_REVIEW/FAILED)

### dispatch_receipt_task

```python
lock_key = f"lock:receipt:{tenant_id}:{file_hash}"
if not acquire_lock(lock_key, ttl_seconds=300):
    raise DuplicateReceiptError(...)
task = process_receipt_task.apply_async(kwargs={...})
return task.id
```

Redis 락 획득 실패 시 `DuplicateReceiptError`. Celery 큐잉 실패 시 락 해제.

### API 엔드포인트 업데이트 (`src/tax_copilot/api/v1/receipts.py`)

DB 커밋 후 `dispatch_receipt_task()` 호출. 반환된 task_id를 `receipts.celery_task_id`에 저장 (별도 UPDATE). Celery/Redis 장애 시 예외를 삼키고 receipt는 PENDING 상태로 유지 — 수동 재처리 가능.

---

## 설계 결정

### DB 커밋 후 디스패치하는 이유

Task를 먼저 dispatch하고 DB commit을 나중에 하면, task가 실행될 때 DB에 receipt가 없어서 `receipt_not_found`를 반환한다. DB commit이 먼저 되어야 task가 안전하게 receipt를 조회할 수 있다.

### Celery result backend를 신뢰하지 않는 이유

Celery result backend는 결과가 소비되면 삭제된다. 사용자에게 보여줄 처리 상태는 항상 `receipts.status` (DB)를 기준으로 한다. Celery task ID는 디버깅용으로만 사용한다.

### asyncio.run() 패턴을 선택한 이유

Celery는 동기 환경에서 동작한다. 프로젝트의 모든 비즈니스 로직은 async로 작성되어 있다. `asyncio.run()`으로 sync → async 경계를 명확하게 한 곳에서만 만든다. Celery 비동기 지원 라이브러리(celery-aio-pool 등)는 성숙도가 낮고 복잡성을 높인다.

### acks_late + Redis 락 두 가지를 함께 사용하는 이유

| 시나리오 | 처리 |
|---------|------|
| 동일 파일 동시 업로드 | Redis 락으로 차단 |
| Worker SIGKILL 후 재큐잉 | acks_late로 재처리, DB 상태 체크로 중복 방지 |
| 락 만료 후 재업로드 | DB unique constraint로 차단 |

둘 다 필요하다. 락만 있으면 worker 재큐잉 시 중복이 발생하고, DB 체크만 있으면 동시 요청을 막지 못한다.

---

## 테스트 결과

`tests/test_celery.py` — 14개 전체 통과:

| 클래스 | 테스트 수 | 내용 |
|--------|---------|------|
| `TestRedisLock` | 5 | 락 획득, 실패, 해제, TTL, 키 독립성 |
| `TestDispatchReceiptTask` | 5 | task_id 반환, 락 설정, 중복 에러, 실패 시 락 해제, 키 형식 |
| `TestProcessAsync` | 4 | APPROVED 스킵, NEEDS_REVIEW 스킵, receipt 없음, PROCESSING 상태 설정 |

fakeredis로 실제 Redis 없이 테스트. `unittest.mock.AsyncMock`으로 DB 세션 모킹.

전체 테스트 스위트: 73개 통과.

---

## Phase 6 예고

- Next.js UI: 로그인, 영수증 업로드, 처리 상태 조회, 세무사 검토 화면
- Railway/Render 배포
- README + 데모 영상

# Phase 5 학습 노트 — Celery 비동기 작업 + Redis 분산 락

> 이 파일은 직접 읽으면서 공부하는 용도로 작성되었습니다.
> Celery, Redis 분산 락, idempotency의 핵심 개념을 다룹니다.

---

## 1. 왜 비동기 작업 큐가 필요한가?

### 문제: HTTP 요청의 타임아웃

FastAPI 엔드포인트에서 직접 LangGraph 워크플로우를 실행하면:
1. 사용자가 영수증을 업로드
2. FastAPI가 Gemini Vision 호출 (2~5초)
3. FastAPI가 Qdrant 검색 (1~2초)
4. FastAPI가 응답 반환

총 3~7초를 HTTP 연결이 열려 있어야 한다. 이 시간 동안:
- 네트워크 타임아웃 발생 가능
- FastAPI worker가 이 요청에 묶여 다른 요청을 처리 못함
- Gemini API 실패 시 HTTP 500 에러를 사용자가 직접 받음

### 해결: 작업 큐 (Task Queue) 패턴

```
[사용자] → [FastAPI] → [DB에 저장] → [즉시 응답: "처리 시작됨"]
                              ↓
                         [Redis Queue]
                              ↓
                         [Celery Worker] → [LangGraph 실행] → [DB 업데이트]
```

FastAPI는 즉시 응답하고, 실제 처리는 백그라운드에서 일어난다. 사용자는 나중에 상태를 폴링한다.

---

## 2. Celery란?

### 기본 구조

```
Producer (FastAPI)     →     Broker (Redis)     →     Consumer (Celery Worker)
task.apply_async()           메시지 큐               process_receipt_task()
```

- **Producer**: 태스크를 큐에 넣는 코드 (FastAPI 엔드포인트)
- **Broker**: 메시지를 보관하는 큐 (Redis 또는 RabbitMQ)
- **Consumer**: 큐에서 메시지를 꺼내 실행하는 프로세스 (Celery worker)
- **Result Backend**: 태스크 실행 결과를 저장하는 곳 (Redis 또는 DB)

### 태스크 정의

```python
# src/tax_copilot/workers/tasks/receipts.py
@celery_app.task(
    name="tax_copilot.workers.tasks.receipts.process_receipt",
    acks_late=True,
    reject_on_worker_lost=True,
    bind=True,
)
def process_receipt_task(self, *, tenant_id, receipt_id, file_path, file_hash, attempt_number=1):
    ...
```

`bind=True`: 태스크 인스턴스(`self`)에 접근 가능. 재시도 횟수(`self.request.retries`) 등을 확인할 수 있다.

### 태스크 디스패치 (큐에 넣기)

```python
task = process_receipt_task.apply_async(kwargs={
    "tenant_id": 1,
    "receipt_id": 10,
    "file_path": "/uploads/receipt.jpg",
    "file_hash": "abc123...",
})
task_id = task.id  # 나중에 상태 추적에 사용
```

---

## 3. acks_late — 가장 중요한 설정

### 기본 동작 (acks_late=False)

```
Worker가 메시지를 큐에서 꺼내자마자 ACK (완료 확인)
→ Worker가 SIGKILL로 죽으면 ACK는 이미 보냈으므로 메시지 재처리 없음
→ 영수증 처리 중에 worker가 죽으면? 처리가 중간에 끊기고 영원히 재처리 안 됨
```

### acks_late=True 동작

```
Worker가 태스크를 완전히 완료한 후에 ACK
→ Worker가 SIGKILL로 죽으면 ACK를 못 보냈으므로 메시지가 재큐잉
→ 다른 Worker가 태스크를 다시 처리
```

```python
celery_app.conf.update(
    task_acks_late=True,             # 완료 후 ACK
    task_reject_on_worker_lost=True, # SIGKILL 시 재큐잉
    worker_prefetch_multiplier=1,    # acks_late와 조합: 1개씩만 처리
)
```

**왜 prefetch_multiplier=1인가?**
기본값(4)이면 worker가 한 번에 4개의 메시지를 꺼내 로컬로 보유한다. worker가 죽으면 꺼내 온 4개 중 처리 중이던 것만 재큐잉되고, 로컬에 있던 나머지 3개는 유실된다. `1`로 설정하면 항상 1개만 처리한다.

---

## 4. Redis 분산 락 (Distributed Lock)

### 문제: 동시 중복 처리

두 명의 사용자가 동시에 같은 파일을 업로드하면:
1. DB unique constraint: `uq_receipts_tenant_file_hash`로 두 번째 INSERT 실패 → OK
2. 하지만 같은 영수증을 두 번 다른 컨텍스트에서 처리하려는 시도는?

더 일반적인 시나리오: worker1이 처리 중인데 worker2가 같은 태스크를 받으면?

### Redis SET NX EX — 원자적 조건부 세팅

```python
# redis-cli로 보면:
SET lock:receipt:1:abc123 "1" NX EX 300
# OK  → 락 획득 성공 (키가 없었음)
# nil → 락 획득 실패 (키가 이미 있음)
```

```python
# Python에서:
result = redis_client.set("lock:receipt:1:abc123", "1", nx=True, ex=300)
# result = True  → 획득 성공
# result = None  → 획득 실패 (이미 잠겨 있음)
```

**NX**: Not eXists — 키가 없을 때만 세팅 (원자적 연산, 경쟁 조건 없음)
**EX**: 만료 시간(초) — worker 장애 시 락이 영원히 잠기지 않도록

```python
# src/tax_copilot/infra/cache/redis_lock.py
def acquire_lock(key: str, ttl_seconds: int = 300) -> bool:
    client = _get_client()
    result = client.set(key, "1", nx=True, ex=ttl_seconds)
    return result is not None
```

### 락 키 설계

```
lock:receipt:{tenant_id}:{file_hash}
```

- `tenant_id`가 포함된 이유: 다른 tenant의 같은 파일 해시가 충돌하지 않도록
- `file_hash`를 쓰는 이유: 같은 파일의 중복 처리를 식별하는 가장 정확한 기준

---

## 5. Idempotency — 여러 번 실행해도 결과가 같아야 한다

### 왜 idempotency가 필요한가?

`acks_late=True`로 설정하면 worker 재시작 시 태스크가 재실행될 수 있다. 재실행 시:
- 영수증이 두 번 처리되면 안 된다
- DB가 두 번 업데이트되면 안 된다

### 전략 1: DB 상태 체크

```python
# src/tax_copilot/workers/tasks/receipts.py
_TERMINAL_STATUSES = {STATUS_APPROVED, STATUS_NEEDS_REVIEW, STATUS_FAILED}

async def _process_async(*, receipt_id, ...):
    # 1. DB에서 현재 상태 확인
    receipt = await db.get(Receipt, receipt_id)

    if receipt.status in _TERMINAL_STATUSES:
        # 이미 완료됨 → 재처리 없이 반환
        return {"status": "skipped", "reason": receipt.status}

    # PENDING 또는 PROCESSING → 처리 진행
    receipt.status = STATUS_PROCESSING
    await db.commit()
    ...
```

### 전략 2: Redis 락 (dispatch 단계)

```python
def dispatch_receipt_task(*, tenant_id, file_hash, ...):
    lock_key = f"lock:receipt:{tenant_id}:{file_hash}"
    if not acquire_lock(lock_key, ttl_seconds=300):
        raise DuplicateReceiptError("이미 처리 중인 영수증입니다.")
    ...
```

두 전략의 역할:

| 상황 | 처리 방법 |
|------|---------|
| 동시에 두 API 요청이 같은 파일 → | Redis 락으로 차단 |
| Worker 재시작으로 태스크 재실행 → | DB 상태 체크로 건너뜀 |
| 락 만료 후 재업로드 → | DB unique constraint로 차단 |

---

## 6. asyncio.run() — sync ↔ async 경계

### 문제: Celery는 동기, 비즈니스 로직은 비동기

```python
# Celery 태스크는 동기 함수다
@celery_app.task(...)
def process_receipt_task(self, *, ...):
    # 여기서 async 함수를 호출하려면?
    result = await _process_async(...)  # SyntaxError! 일반 함수에서 await 불가
```

### 해결: asyncio.run()

```python
@celery_app.task(...)
def process_receipt_task(self, *, tenant_id, ...):
    # asyncio.run()이 새 이벤트 루프를 만들고 async 함수를 실행한다
    return asyncio.run(
        _process_async(tenant_id=tenant_id, ...)
    )

async def _process_async(*, tenant_id, ...):
    async with AsyncSessionLocal() as db:
        ...  # async/await 자유롭게 사용 가능
```

**주의**: `asyncio.run()`은 호출될 때마다 새 이벤트 루프를 만든다. 이미 실행 중인 이벤트 루프 안에서 호출하면 오류가 발생한다. Celery worker는 동기 환경이므로 이미 실행 중인 루프가 없어서 안전하다.

---

## 7. DB 커밋 후 Celery 디스패치하는 이유

### 잘못된 순서

```python
task_id = dispatch_receipt_task(...)  # 큐에 넣음
await db.commit()                      # DB에 저장
```

Worker가 task를 받아서 receipt_id로 DB를 조회하면? commit이 안 됐으니 receipt가 없다.
→ `receipt_not_found` 오류

### 올바른 순서

```python
await db.commit()                      # DB에 먼저 저장
task_id = dispatch_receipt_task(...)  # 그 다음 큐에 넣음
```

DB에 확정된 후 worker가 처리 시작 → 항상 receipt를 찾을 수 있다.

---

## 8. Celery Result Backend를 신뢰하지 않는 이유

Celery result backend (Redis에 저장된 태스크 결과)는 소비된 후 삭제되거나 만료된다. 사용자에게 보여줄 처리 상태는 항상 `receipts.status` (PostgreSQL)를 기준으로 한다.

```python
# receipts.py API endpoint
@router.get("/{receipt_id}")
async def get_receipt_status(receipt_id: int, ...):
    receipt = await db.get(Receipt, receipt_id)
    return ReceiptStatusResponse(
        receipt_id=receipt.id,
        status=receipt.status,  # DB가 진실의 원천 (source of truth)
        ...
    )
```

Celery task ID (`celery_task_id` 컬럼)는 디버깅과 운영 모니터링에만 사용한다.

---

## 9. Celery Worker 실행 방법 (실습용)

실제 개발 환경에서 worker를 시작하려면:

```bash
# Redis가 실행 중이어야 함
docker run -d -p 6379:6379 redis:7

# Celery worker 시작 (프로젝트 루트에서)
celery -A tax_copilot.workers.celery_app worker --loglevel=info

# 별도 터미널에서 FastAPI 시작
uvicorn tax_copilot.api.main:app --reload
```

```bash
# 태스크 모니터링 (Flower)
pip install flower
celery -A tax_copilot.workers.celery_app flower
# http://localhost:5555 에서 확인
```

---

## 핵심 질문 목록 (면접 준비)

1. "Celery의 acks_late=True가 왜 중요한가요?"
2. "Redis SET NX EX가 일반 GET/SET과 다른 점은?"
3. "worker_prefetch_multiplier=1로 설정하는 이유는?"
4. "Celery 태스크가 두 번 실행되는 경우를 어떻게 방지하나요?"
5. "asyncio.run()을 Celery 태스크 안에서 사용하는 이유는?"
6. "Celery result backend가 있는데 왜 DB에 별도로 상태를 저장하나요?"
7. "DB commit 후에 Celery task를 dispatch하는 이유는?"
8. "Redis 락의 TTL을 300초로 설정한 이유는? 너무 길거나 짧으면?"
9. "worker가 SIGKILL로 죽었을 때 영수증 처리는 어떻게 되나요?"
10. "dispatch_receipt_task에서 Celery 큐잉이 실패하면 락을 왜 해제하나요?"

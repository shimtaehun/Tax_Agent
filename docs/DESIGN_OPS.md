# Tax-Copilot Design — OPS (16~21장)

본 문서는 전체 설계 문서를 4개 모듈 + 1개 인덱스로 분할한 것 중 **OPS 모듈**입니다.
DB 스키마, 인증/보안/감사 로그, 관측 가능성 (structlog, PII 마스킹, 도메인 예외), Graceful Degradation, 테스트 전략, 배포·비용·환경 분리를 다룹니다.
도메인 모델은 DESIGN_CORE.md 9장, 에이전트 동작 흐름은 DESIGN_AGENT.md 참조.

Version: 5.1 (분할판)

---

## 16. 데이터베이스 스키마

### 핵심 테이블

```text
tenants
users
client_companies
receipts
receipt_items
tax_judgments
law_sources
law_chunks
audit_events
```

### Tenant

```python
class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

### ClientCompany

```python
class ClientCompany(Base):
    __tablename__ = "client_companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    business_no: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 마스킹 대상
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "business_no", name="uq_client_companies_tenant_bno"),
    )
```

MVP에서는 tenant별 default client company를 seed해 고객사 선택 UI 없이 업로드 흐름을 먼저 완성한다.

### User

```python
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="client")
    is_active: Mapped[bool] = mapped_column(default=True)

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )
```

### Receipt

```python
class Receipt(Base):
    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_company_id: Mapped[int] = mapped_column(ForeignKey("client_companies.id"), index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    file_path: Mapped[str] = mapped_column(String(500))
    file_hash: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int]

    transaction_date: Mapped[date | None] = mapped_column(nullable=True)
    parsed_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    langgraph_thread_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    attempt_number: Mapped[int] = mapped_column(default=1)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    review_comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime] = mapped_column(default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("tenant_id", "file_hash", name="uq_receipts_tenant_file_hash"),
    )
```

### TaxJudgment

```python
class TaxJudgment(Base):
    __tablename__ = "tax_judgments"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    receipt_id: Mapped[int] = mapped_column(ForeignKey("receipts.id"), index=True)

    decision_data: Mapped[dict] = mapped_column(JSON)
    calculation_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    citations: Mapped[list[dict]] = mapped_column(JSON)

    prompt_version: Mapped[str] = mapped_column(String(50))
    model_name: Mapped[str] = mapped_column(String(100))
    law_corpus_version: Mapped[str] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

### AuditEvent

```python
class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("receipts.id"), nullable=True)

    event_type: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=func.now())
```

### JSON 컬럼 변경 감지

SQLAlchemy JSON 내부 값을 직접 수정하면 변경 감지가 안 될 수 있다. dict 전체 재할당을 기본 원칙으로 한다.

```python
receipt.parsed_data = {
    **(receipt.parsed_data or {}),
    "merchant_name": "ABC",
}
```

## 17. 인증, 보안, 감사 로그

### 인증

- JWT 기반 인증
- `tenant_id` claim 포함
- role: `client`, `staff`, `admin`
- admin API에는 `require_admin`
- 모든 DB query에 tenant scope 적용

### 보안 원칙

- API key는 `.env` 또는 secret manager
- R2 bucket은 private
- presigned URL은 짧은 TTL
- 로그에 OCR 원문 전체를 무조건 남기지 않는다.
- 외부 LLM API로 전송되는 데이터 범위를 문서화한다.
- 개인정보와 세무자료 삭제 정책을 README에 명시한다.

### 감사 로그 이벤트 예시

```text
RECEIPT_UPLOADED
RECEIPT_PROCESSING_STARTED
AI_EXTRACTION_COMPLETED
RAG_SEARCH_COMPLETED
AI_DECISION_DRAFTED
HUMAN_REVIEW_REQUESTED
HUMAN_REVIEW_APPROVED
HUMAN_REVIEW_REJECTED
RECEIPT_PROCESSING_FAILED
```

## 18. 관측 가능성과 에러 처리

### 18.1. 구조화 로깅 (structlog)

기본 stdlib logging의 free-form 문자열은 운영 환경에서 검색·필터·집계가 어렵다. JSON 출력 기반 구조화 로깅으로 시작한다.

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "receipt.upload.accepted",
    tenant_id=tenant_id,
    receipt_id=receipt_id,
    file_size_bytes=size,
    mime_type=mime,
)
```

장점:

- 로그 메시지 자체가 키-값 구조
- LangSmith, Datadog, Grafana Loki 등으로 쉽게 연동
- 면접 talking point로 활용 가능

### 18.2. request_id 전파

FastAPI 미들웨어에서 `request_id`를 생성해 `contextvars`에 저장하고, 모든 로그에 자동 첨부한다.

```python
import contextvars
import uuid
from starlette.middleware.base import BaseHTTPMiddleware

request_id_var = contextvars.ContextVar("request_id", default="")

class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = request_id
            return response
        finally:
            request_id_var.reset(token)
```

Celery worker에서도 task 인자로 `request_id`를 받아 동일한 contextvar에 저장한다. 이로써 HTTP 요청 -> 비동기 작업 -> LangGraph 노드 전체에 걸쳐 단일 추적 ID가 유지된다.

### 18.3. 도메인 예외 계층

도메인 로직과 HTTP 응답을 분리하기 위해 `core/exceptions.py`에 예외 트리를 정의한다.

```python
class TaxAgentError(Exception):
    """Base exception for all domain errors."""

class ValidationError(TaxAgentError):
    """Invalid input that should be rejected with HTTP 400."""

class DuplicateReceiptError(TaxAgentError):
    """Receipt already processed for this tenant. HTTP 409."""

class ExtractionFailedError(TaxAgentError):
    """Vision extraction returned unusable output. HTTP 422."""

class LawCorpusVersionMismatch(TaxAgentError):
    """Requested as_of_date is not covered by current corpus. HTTP 503."""

class HumanReviewRequiredError(TaxAgentError):
    """Decision needs human approval, not an actual error."""
```

API 레이어(`api/errors.py`)에서 예외-HTTP 상태 매핑을 일괄 처리한다. 도메인 코드는 HTTP 상태 코드를 알 필요가 없다.

### 18.4. PII 마스킹

감사 로그와 일반 로그 모두에서 다음 필드는 자동 마스킹한다.

- 사업자등록번호: `123-45-67890` → `123-XX-XXXXX`
- 신용카드번호: 전체 마스킹 (`****-****-****-1234`)
- 주민등록번호: 절대 저장 금지
- 영수증 OCR 원문: 길이 제한 또는 hash로만 저장

structlog processor에서 일괄 처리한다.

```python
def mask_pii(logger, method_name, event_dict):
    if "business_no" in event_dict:
        event_dict["business_no"] = mask_business_no(event_dict["business_no"])
    if "card_number" in event_dict:
        event_dict["card_number"] = "****-****-****-XXXX"
    return event_dict
```

### 18.5. LangSmith tracing

LangGraph 실행은 LangSmith로 trace한다. 환경 변수만 설정하면 자동 연동된다.

```text
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=tax-copilot
```

운영 환경에서 LLM 호출 비용 추적과 디버깅에 매우 유용하다. 다만 외부 서비스이므로 민감 데이터는 trace에 포함되지 않도록 input filtering을 적용한다.

### 18.6. 후순위: OpenTelemetry

분산 trace까지 필요해지면 OpenTelemetry로 확장한다. MVP에서는 structlog + LangSmith로 충분하다.

## 19. Graceful Degradation

### 외부 서비스 실패 시 원칙

- Gemini 실패: retry 후 `NEEDS_REVIEW`
- Qdrant 실패: fallback search 후 confidence 낮게 처리
- R2 read 실패: `FAILED` 또는 재시도
- law corpus 없음: 자동 판단 금지
- Checkpointer 실패: HITL 기능 중단이므로 작업 실패 처리

### 단계별 구현

MVP:

- timeout
- retry
- 실패 상태 저장
- admin 화면에서 실패 사유 표시

후순위:

- circuit breaker
- dead letter queue
- alerting
- service health dashboard

## 20. 테스트 전략

### Unit Test

- VAT 계산
- 접대비 한도 계산
- 날짜 기준 법령 필터
- chunk id 생성
- file validation
- JSON 재할당 로직
- risk flag 판정

### Integration Test

- upload to task dispatch
- LangGraph low-risk candidate save flow
- LangGraph HITL interrupt and resume
- Qdrant search with as_of_date
- Celery retry and idempotency

### RAG Evaluation

MVP에서는 수동 smoke test로 시작한다. RAGAS는 gold dataset이 생긴 뒤 도입한다.

RAGAS 도입 조건:

- 최소 20개 이상의 검증 질문
- 각 질문에 ground truth와 근거 조문 존재
- 법령 corpus version 고정
- README에는 실측값만 게시

## 21. 배포·비용·환경 분리

### 21.1. 비용 표현

기존 "Zero-Cost Strategy"는 "Free-Tier-First Strategy"로 바꾼다.

이유:

- 무료 티어는 변경될 수 있다.
- request 수, storage, token 사용량에 따라 비용이 발생할 수 있다.
- 면접에서는 무조건 0원보다 비용 계측과 확장 경로가 더 설득력 있다.

### 21.2. 비용 계측 항목

- LLM input/output token
- embedding token
- Qdrant vector count
- R2 storage usage
- R2 Class A/B operations
- Celery processing time
- receipt당 평균 비용

### 21.3. 환경 분리

세 환경을 분리한다.

| 환경 | 용도 | DB | 외부 서비스 |
| --- | --- | --- | --- |
| dev | 로컬 개발 | Docker Compose PG | mock 또는 실제 Gemini (적은 호출) |
| test | 자동 테스트 | testcontainers PG | 전부 mock |
| prod | Render/Railway 배포 | managed PG | 실제 외부 서비스 |

각 환경은 별도 `.env` 파일을 사용한다.

```text
.env.example        # 추적, 실제 값 없음
.env.dev            # 로컬 dev (git ignore)
.env.test           # CI/local test (git ignore)
.env.prod           # 배포 환경 (git ignore, 실제로는 플랫폼 env vars)
```

### 21.4. 시크릿 관리

- 로컬: `.env` 파일 + python-dotenv 자동 로드
- CI: GitHub Actions secrets
- 배포: Render env vars 또는 Railway variables

다음은 절대 git에 들어가면 안 된다.

- API keys (Gemini, LangSmith, Qdrant, R2)
- JWT signing key
- DB password
- Redis password

`pre-commit` hook에 `detect-secrets`를 포함시켜 사전 차단한다.

### 21.5. API 버저닝

모든 API endpoint는 `/api/v1/` prefix를 사용한다. breaking change 시 `/api/v2/`를 병행하고, 일정 기간 후 v1을 deprecate한다.

```python
from fastapi import APIRouter

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(receipts_router)
v1_router.include_router(reviews_router)
```

### 21.6. Rate Limiting

MVP에서는 단순 카운터 기반 rate limiter를 적용한다.

- tenant당 LLM 호출: 1시간에 100회
- 사용자당 영수증 업로드: 1시간에 50회
- 인증되지 않은 endpoint: IP당 1분에 20회

후순위로 Redis 기반 sliding window rate limiter를 도입한다.

### 21.7. Qdrant Cloud 주의

Qdrant free cluster는 prototype/test 용도다. 2026년 기준 free cluster는 single node, 1GB RAM, 0.5 vCPU, 4GB disk 수준이며 inactive cluster suspension/deletion 조건이 있다.

참고: https://qdrant.tech/documentation/cloud/create-cluster/

### 21.8. 배포 플랫폼 비교

| 플랫폼 | 장점 | 단점 |
| --- | --- | --- |
| Render | UI 직관적, Free Web Service와 Background Worker 지원 | Free Postgres 30일 만료, Free Key Value는 재시작 시 데이터 유실, 콜드 스타트 |
| Railway | 신규 trial $5 크레딧, 이후 Free plan 월 $1 크레딧, 모든 서비스 한 곳에서 관리 | 리소스 사용량이 크레딧을 넘으면 유료, trial/Free 조건 확인 필요 |

이 프로젝트에서는 Railway를 1순위, Render를 2순위로 검토한다. Celery worker가 필요하므로 Background Worker 지원이 중요하다. 단, 두 플랫폼 모두 장기 무료 운영을 보장하지 않으므로 배포 직전에 현재 가격과 제한을 다시 확인한다.


---

## 관련 문서

- **DESIGN_INDEX.md** — 전체 프로젝트 1~200줄 요약 (이것부터 읽기)
- **DESIGN_CORE.md** — 개요, 원칙, 법적 포지셔닝, MVP, 기술 결정, 스택, 아키텍처, 폴더 구조, 도메인 모델 (1~9장)
- **DESIGN_AGENT.md** — LangGraph, HITL, RAG, 법령 수집, Vision, Celery (10~15장)
- **DESIGN_OPS.md** — DB, 인증, 관측, Graceful Degradation, 테스트, 배포 (16~21장)
- **DESIGN_PLAN.md** — 개발 로드맵, 일정, 백로그, 함정, 시연 자료, README, 부록 (22~29장)

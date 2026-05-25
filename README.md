# Tax-Copilot

세무사를 위한 AI 영수증 검토 시스템. 반복 업무는 자동화하고, 최종 판단은 세무사가 합니다.

> 본 시스템은 세무사의 업무를 보조하는 도구이며, 모든 세무 판단의 최종 책임은
> 사용 세무사에게 있습니다. AI가 제공하는 분석 결과는 참고용 후보이며,
> 세무신고 및 세무대리는 세무사법에 따라 세무사 자격이 있는 자만이 수행할 수 있습니다.

---

## 주요 기능

- **영수증 이미지 파싱**: Gemini Vision으로 상호명, 금액, 날짜, 증빙 종류를 자동 추출
- **법령 검색 (RAG)**: 거래일 기준으로 유효한 부가가치세법 / 법인세법 조항을 벡터 검색
- **세무 판단 자동화**: 증빙 종류별 부가세 공제 가능 여부, risk_flag 자동 생성
- **HITL 워크플로우**: AI 판단을 세무사가 승인/반려하는 Human-in-the-Loop 흐름
- **비동기 처리**: Celery + Redis로 영수증 처리를 백그라운드에서 실행

---

## 아키텍처

```
[Next.js UI]
     │
     ▼ REST API
[FastAPI]
     │
     ├─── [PostgreSQL] ── 영수증/사용자/감사 로그
     │
     ├─── [Redis Queue] ── Celery 태스크 브로커
     │
     └─── [Celery Worker]
               │
               ├─── [LangGraph] ── 6노드 워크플로우 + HITL
               │         │
               │         ├─── [Gemini Vision] ── 영수증 파싱
               │         ├─── [Gemini Embedding + Qdrant] ── 법령 RAG
               │         └─── [Rule Engine] ── 세무 판단
               │
               └─── [PostgreSQL Checkpointer] ── HITL 상태 보존
```

### 헥사고날 아키텍처 (의존성 방향)

```
api/ workers/ agents/   사용 계층
        ↓
     infra/             외부 시스템 어댑터 (Gemini, Qdrant, Redis)
        ↓
      core/             순수 도메인 (pydantic + 표준 라이브러리만)
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| Backend | FastAPI, SQLAlchemy (async), Alembic |
| AI / ML | LangGraph, Gemini Vision, Gemini Embedding |
| Vector DB | Qdrant |
| 비동기 큐 | Celery 5, Redis |
| 인증 | JWT (python-jose), bcrypt |
| 로깅 | structlog (JSON) |
| Frontend | Next.js 15 (App Router), TypeScript |
| 테스트 | pytest-asyncio, fakeredis, unittest.mock |
| DB | PostgreSQL 16 |

---

## LangGraph 워크플로우 (6노드)

```
image_quality_node
    ├─ unreadable → reject_unreadable_node → END
    └─ ok → intake_node (Gemini Vision)
                 └─ retrieval_node (Qdrant RAG)
                          └─ calculation_node (Decimal VAT)
                                   └─ audit_prepare_node (rule-based)
                                            ├─ requires_human=False → save_result_node → END
                                            └─ requires_human=True → human_review_node (interrupt)
                                                                           └─ resume → save_result_node → END
```

**Graceful Degradation**: Gemini API 장애 → `confidence=0.0` fallback → `requires_human=True` → 세무사 판단

---

## 로컬 개발 환경 설정

### 사전 요구사항

- Python 3.11+
- Node.js 20+
- Docker (PostgreSQL, Redis, Qdrant 실행용)

### 백엔드 설정

```bash
# 1. Python 의존성 설치
pip install pip-tools
pip-compile requirements/base.in -o requirements/base.txt
pip-compile requirements/dev.in -o requirements/dev.txt
pip install -r requirements/dev.txt
pip install -e .

# 2. 인프라 실행
docker compose up -d

# 3. DB 마이그레이션
alembic upgrade head

# 4. 초기 데이터 (관리자 계정, 법령 코퍼스)
python scripts/seed_admin.py
python scripts/seed_law_corpus.py

# 5. FastAPI 실행
uvicorn tax_copilot.api.main:app --reload --port 8000

# 6. Celery Worker 실행 (별도 터미널)
celery -A tax_copilot.workers.celery_app worker --loglevel=info
```

### 프론트엔드 설정

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

### 환경 변수 (.env)

```
DATABASE_URL=postgresql+asyncpg://tax:tax@localhost:5432/tax_copilot
REDIS_URL=redis://localhost:6379/0
SECRET_KEY=dev-secret-change-in-production
GEMINI_API_KEY=your-key-here
QDRANT_URL=http://localhost:6333
FRONTEND_URL=http://localhost:3000
```

---

## 테스트

```bash
# 전체 테스트 (73개)
PYTHONPATH=src pytest

# 특정 모듈
PYTHONPATH=src pytest tests/test_celery.py -v
PYTHONPATH=src pytest tests/test_vision.py -v
PYTHONPATH=src pytest tests/test_rag.py -v
```

| 파일 | 테스트 수 | 내용 |
|------|---------|------|
| test_auth.py | 11 | JWT, bcrypt, 권한 |
| test_graph.py | 12 | LangGraph 워크플로우, HITL |
| test_rag.py | 11 | LawChunk, Qdrant, 날짜 필터 |
| test_validation.py | 14 | magic bytes, SHA-256, 파일 크기 |
| test_vision.py | 22 | Gemini Vision, Pillow, ParsedReceipt |
| test_celery.py | 14 | Redis 락, dispatch, idempotency |
| test_healthz.py | 1 | 헬스체크 |

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | /api/v1/auth/login | 로그인, JWT 발급 |
| POST | /api/v1/receipts | 영수증 업로드 |
| GET | /api/v1/receipts/{id} | 처리 상태 조회 |
| GET | /api/v1/reviews/pending | 검토 대기 목록 |
| POST | /api/v1/reviews/{id}/decide | 승인/반려 |
| GET | /healthz | 헬스체크 |

---

## 배포 (Render)

`render.yaml`에 API 서버와 Celery Worker 두 서비스가 정의되어 있다.

필요한 환경 변수:
- `DATABASE_URL` — PostgreSQL 연결 문자열
- `REDIS_URL` — Redis 연결 문자열
- `GEMINI_API_KEY` — Google AI Studio API 키
- `QDRANT_URL` — Qdrant 클라우드 또는 자체 호스팅 URL
- `FRONTEND_URL` — Next.js 배포 URL (CORS 허용)

---

## Phase별 구현 내용

| Phase | 내용 |
|-------|------|
| 0 | src layout, Docker Compose, FastAPI, SQLAlchemy, Alembic, structlog |
| 1 | JWT 인증, bcrypt, DB 모델 5개, magic bytes 검증, 감사 로그 |
| 2 | LangGraph 6노드 워크플로우, HITL interrupt/resume, Decimal VAT |
| 3 | LawChunk, Gemini Embedding, Qdrant, 거래일 기준 법령 검색 |
| 4 | Gemini Vision structured output, Pillow 품질 체크, risk_flags |
| 5 | Celery + Redis 분산 락, acks_late idempotency |
| 6 | Next.js UI, CORS, render.yaml, README |

---

## 학습 노트

각 Phase별 상세 학습 노트가 `docs/LEARNING_NOTES/`에 있습니다.
면접 질문 목록과 설계 결정 이유가 포함되어 있습니다.

# Tax-Copilot — 세무사를 위한 AI 영수증 검토 시스템

반복 업무는 자동화하고, 최종 판단은 세무사가 합니다. 영수증을 올리면 AI가 파싱·법령 검색·세무 판단까지 후보를 만들어 오고, 세무사는 그 결과를 승인하거나 반려합니다.

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square&logo=langchain&logoColor=white" alt="LangGraph" />
  <img src="https://img.shields.io/badge/Gemini-4285F4?style=flat-square&logo=google&logoColor=white" alt="Gemini" />
  <img src="https://img.shields.io/badge/Qdrant-DC244C?style=flat-square&logo=qdrant&logoColor=white" alt="Qdrant" />
  <img src="https://img.shields.io/badge/Celery-37814A?style=flat-square&logo=celery&logoColor=white" alt="Celery" />
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=nextdotjs&logoColor=white" alt="Next.js" />
</p>

<p align="center">
  <b>1인 개발</b> · 백엔드 · AI 파이프라인 · 프론트엔드 · 테스트 166개 · 2026.05 ~
</p>

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
- **전자세금계산서 관리**: 홈택스 XML/CSV 매입·매출 세금계산서 가져오기, 검토·수정
- **부가세 집계**: 기간별 매입세액 자동 집계
- **세무조사 리스크 스코어링**: 고객사별 리스크 점수 산출
- **신고 기한 관리**: 한 해 신고 기한 일괄 생성 및 완료 추적
- **월간 정산 리포트**: 영수증·세금계산서 지표를 인쇄용 HTML(PDF 저장)로 출력
- **고객사 포털**: client 역할 전용 대시보드 (영수증 상태 집계)

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

## 만들면서 한 선택들

### AI가 "최종 판단"을 하지 않게 설계했다

세무신고는 세무사법상 자격이 있는 사람만 할 수 있고, 잘못된 판단의 책임도 사람에게 있습니다. 그래서 AI는 끝까지 **후보만 제시**하고 결정은 사람이 하도록 못 박았습니다. LangGraph의 `interrupt`로 워크플로우를 사람 검토 지점에서 멈추고, 세무사가 승인/반려하면 `resume`으로 이어서 진행합니다. 자동화의 편리함과 법적 책임 구조를 둘 다 지키기 위한 핵심 설계입니다.

### 부가세 계산은 절대 float를 쓰지 않았다

`0.1 + 0.2 != 0.3`인 부동소수점으로 세금을 계산하면 원 단위에서 오차가 누적됩니다. 세금은 1원도 틀리면 안 되는 도메인이라, 금액 계산 전 구간에서 `Decimal`을 사용하고 반올림 정책을 명시적으로 고정했습니다. "성능상 float가 빠르다"보다 "정확성이 곧 신뢰"라는 판단이었습니다.

### 법령은 "거래일 기준"으로 검색한다

세법은 개정됩니다. 2023년 거래를 2025년 개정 조항으로 판단하면 틀린 결과가 나옵니다. 그래서 법령을 벡터 DB(Qdrant)에 넣을 때 시행일·폐지일 메타데이터를 함께 저장하고, RAG 검색 시 **거래일에 유효했던 조항만** 필터링합니다. "지금 법"이 아니라 "그때 법"으로 판단하는 게 세무에서는 정확성의 전제였습니다.

### 같은 영수증을 두 번 처리하지 않게 했다

비동기 큐(Celery)에서는 재시도·중복 전달이 일어날 수 있습니다. 같은 영수증이 두 번 판단되면 결과가 꼬이므로, Redis 분산 락으로 동시 처리를 막고 `acks_late`로 작업이 실제로 끝난 뒤에만 ack 하도록 했습니다. 워커가 도중에 죽어도 작업이 유실되지 않고, 중복 실행돼도 결과가 한 번만 반영되는 멱등성을 확보했습니다.

### 의존성 방향을 한쪽으로만 흐르게 했다 (헥사고날)

`core/`(순수 도메인)는 Gemini·Qdrant·Redis 같은 외부 시스템을 전혀 모르고, 바깥 계층만 안쪽을 의존하도록 방향을 고정했습니다. 덕분에 외부 API 없이도 도메인 로직을 단위 테스트할 수 있었고, AI 장애 상황(Graceful Degradation)도 어댑터 계층에서만 처리하면 돼서 전체가 단순해졌습니다. 현재 테스트 166개 중 상당수가 외부 의존 없이 빠르게 도는 것도 이 구조 덕분입니다.

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
# 전체 테스트 (166개)
PYTHONPATH=src pytest

# 특정 모듈
PYTHONPATH=src pytest tests/test_celery.py -v
PYTHONPATH=src pytest tests/test_vision.py -v
PYTHONPATH=src pytest tests/test_rag.py -v
```

주요 테스트 파일 (총 21개 파일, 166개 테스트):

| 파일 | 테스트 수 | 내용 |
|------|---------|------|
| test_vision.py | 34 | Gemini Vision, Pillow, ParsedReceipt |
| test_validation.py | 17 | magic bytes, SHA-256, 파일 크기 |
| test_celery.py | 14 | Redis 락, dispatch, idempotency |
| test_auth.py | 12 | JWT, bcrypt, 권한 |
| test_graph.py | 11 | LangGraph 워크플로우, HITL |
| test_rag.py | 11 | LawChunk, Qdrant, 날짜 필터 |
| test_risk.py | 9 | 세무조사 리스크 스코어링 |
| test_vat.py | 9 | 부가세 매입세액 집계 |
| test_deadlines.py | 9 | 신고 기한 생성·완료 |
| test_client_role.py | 7 | 고객 포털 역할 기반 접근 |
| test_tax_invoices.py | 5 | 세금계산서 import·수정·삭제 |
| 그 외 | 28 | explanation, batch, comments, sse, portal, law_open_data 등 |

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| POST | /api/v1/auth/login | 로그인, JWT 발급 |
| POST | /api/v1/receipts | 영수증 업로드 |
| GET | /api/v1/receipts/{id} | 처리 상태 조회 |
| GET | /api/v1/reviews/pending | 검토 대기 목록 |
| POST | /api/v1/reviews/{id}/decide | 승인/반려 |
| GET | /api/v1/vat/summary | 기간별 부가세 매입세액 집계 |
| GET | /api/v1/risk/score | 세무조사 리스크 점수 |
| GET | /api/v1/deadlines | 신고 기한 목록 |
| POST | /api/v1/deadlines/generate | 한 해 신고 기한 일괄 생성 |
| POST | /api/v1/tax-invoices/upload | 홈택스 세금계산서 import |
| GET | /api/v1/monthly-reports | 월간 정산 지표 |
| GET | /api/v1/portal/dashboard | 고객사 대시보드 (client 전용) |
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
| 7+ | 세금계산서 관리, 부가세 집계, 리스크 스코어링, 신고 기한, 월간 리포트, 고객 포털 |

---

## 학습 노트

각 Phase별 상세 학습 노트가 `docs/LEARNING_NOTES/`에 있습니다.
면접 질문 목록과 설계 결정 이유가 포함되어 있습니다.

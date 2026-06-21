<div align="center">

<br/>

# 🧾 Tax-Copilot

### 세무사를 위한 AI 영수증 검토 시스템

반복 업무는 자동화하고, 최종 판단은 세무사가 합니다.<br/>
영수증을 올리면 AI가 파싱·법령 검색·세무 판단까지 후보를 만들어 오고,<br/>
세무사는 그 결과를 승인하거나 반려합니다.

<br/>

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square&logo=langchain&logoColor=white)
![Gemini](https://img.shields.io/badge/Gemini-4285F4?style=flat-square&logo=google&logoColor=white)
![Qdrant](https://img.shields.io/badge/Qdrant-DC244C?style=flat-square&logo=qdrant&logoColor=white)
![Celery](https://img.shields.io/badge/Celery-37814A?style=flat-square&logo=celery&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-000000?style=flat-square&logo=nextdotjs&logoColor=white)

<br/>

`1인 개발`  ·  백엔드 · AI 파이프라인 · 프론트엔드  ·  테스트 240여 개  ·  2026.05 ~

</div>

<br/>

> [!IMPORTANT]
> 본 시스템은 세무사의 업무를 보조하는 도구이며, 모든 세무 판단의 최종 책임은 사용 세무사에게 있습니다. AI가 제공하는 분석 결과는 참고용 후보이며, 세무신고 및 세무대리는 세무사법에 따라 세무사 자격이 있는 자만이 수행할 수 있습니다.

<br/>

---

## 📑 목차

- [🖥 화면 미리보기](#-화면-미리보기)
- [✨ 주요 기능](#-주요-기능)
- [⚙️ 반복 업무 자동화 5종](#️-반복-업무-자동화-5종)
- [🧱 아키텍처](#-아키텍처)
- [🛠 기술 스택](#-기술-스택)
- [🗄 데이터베이스 구조](#-데이터베이스-구조)
- [🔀 LangGraph 워크플로우](#-langgraph-워크플로우-6노드)
- [💡 만들면서 한 선택들](#-만들면서-한-선택들)
- [🚀 로컬 개발 환경 설정](#-로컬-개발-환경-설정)
- [🧪 테스트](#-테스트)
- [🔌 API 엔드포인트](#-api-엔드포인트)
- [📦 배포 (Render)](#-배포-render)
- [🗂 Phase별 구현 내용](#-phase별-구현-내용)

<br/>

---

## 🖥 화면 미리보기

> Next.js 15 App Router 기반의 다크 셸 UI. 영수증 검토(HITL) · 세금계산서 · 카드내역 · 월별 마감 리포트를 한 워크스페이스에서 다룹니다.

<table>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/assets/screenshots/01-receipt-review.png" alt="영수증 검토 — AI 판단 초안 + 법령 검색 + 세무사 승인" />
      <p align="center"><b>🧾 영수증 검토 (HITL)</b><br/><sub>Gemini Vision 파싱 → 법령 RAG 인용 → AI 판단 초안 → 세무사 승인/반려</sub></p>
    </td>
    <td width="50%" valign="top">
      <img src="docs/assets/screenshots/02-tax-invoices.png" alt="세금계산서 관리 — 홈택스 XML/CSV import" />
      <p align="center"><b>📄 세금계산서 관리</b><br/><sub>홈택스 전자세금계산서 XML/CSV import, 매입·매출 분류, 세액 집계</sub></p>
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <img src="docs/assets/screenshots/03-card-statements.png" alt="카드내역 관리 — 카드사 엑셀 import + 계정과목 자동 분류" />
      <p align="center"><b>💳 카드내역 관리</b><br/><sub>카드사 엑셀 업로드, 거래처별 계정과목 자동 분류·학습</sub></p>
    </td>
    <td width="50%" valign="top">
      <img src="docs/assets/screenshots/04-monthly-report.png" alt="월별 마감 리포트 — 매입·매출세액, 예상 납부세액, AI 요약" />
      <p align="center"><b>📊 월별 마감 리포트</b><br/><sub>매입·매출세액·예상 납부세액 정산, 시각화, AI 리포트 요약 + HTML 다운로드</sub></p>
    </td>
  </tr>
</table>

<br/>

---

## ✨ 주요 기능

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

<br/>

---

## ⚙️ 반복 업무 자동화 5종

세무사가 매달 손으로 반복하던 노동을 직접 줄이는 기능 묶음입니다. 핵심 판단 로직은 모두 `core/`의 **순수 함수**(외부 라이브러리 없음, 단위 테스트 100%)로 두고, API·worker는 호출만 합니다.

| # | 기능 | 무엇을 자동화하나 | 핵심 모듈 |
|---|------|------------------|-----------|
| **F1** | **분개(전표) 자동 생성 + CSV export** | 승인된 영수증·세금계산서를 복식부기 차/대변 전표로 변환, 더존·세무사랑이 그대로 읽는 일반전표 CSV(UTF-8 BOM)로 내보내 "재입력" 단계를 제거 | `core/tax/journal.py`, `journal_export.py` |
| **F2** | **거래처별 계정과목 규칙 학습** | 가맹점→계정과목을 한 번 정하면 다음부터 자동 적용 (완전일치 > 부분포함 우선, 키워드 분류기보다 우선) | `core/tax/account_rules.py` |
| **F3** | **삼중 대사 (통장↔카드↔세금계산서)** | 통장 입출금을 카드·세금계산서 기반 예상 현금흐름과 매칭, "근거 없는 입출금"·"통장 미반영"만 추려냄 | `core/tax/reconciliation.py`, `core/bank.py` |
| **F4** | **누락 증빙 감지 + 고객 요청 문구** | 카드 결제 중 대응 영수증이 없는 건을 가려내고, 고객에게 보낼 요청 문구까지 생성 | `core/tax/missing_evidence.py` |
| **F5** | **고객사별 월마감 체크리스트** | 매달 반복되는 마감 절차를 표준 8단계 템플릿(자료수집→검토→분류→대사→누락증빙→집계→분개→신고)으로 만들고 진행률 추적 | `core/tax/monthly_closing.py` |

> [!NOTE]
> F1~F5는 도메인·API·마이그레이션(0010~0012)·테스트까지 구현되어 있습니다. 분개 미리보기·대사 보드·누락 증빙·월마감 체크리스트의 전용 프론트엔드 화면은 후속 작업입니다.

<br/>

---

## 🧱 아키텍처

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

<br/>

---

## 🛠 기술 스택

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

<br/>

---

## 🗄 데이터베이스 구조

PostgreSQL 16 기반의 **멀티테넌트** 구조입니다. 최상위 `tenants`(세무사 사무소) 아래에 `client_companies`(고객사)와 `users`가 속하고, 영수증·세금계산서·신고 기한이 고객사 단위로 관리됩니다. 거의 모든 테이블이 `tenant_id`를 가져 사무소 간 데이터가 격리됩니다.

```mermaid
erDiagram
    tenants ||--o{ client_companies : "고객사 보유"
    tenants ||--o{ users : "직원/고객 소속"
    client_companies ||--o{ users : "client 계정 소속"
    client_companies ||--o{ receipts : "영수증"
    client_companies ||--o{ tax_invoices : "세금계산서"
    client_companies ||--o{ filing_deadlines : "신고 기한"
    users ||--o{ receipts : "업로드/검토"
    receipts ||--o{ receipt_comments : "코멘트"
    users ||--o{ receipt_comments : "작성"
    receipts ||--o{ audit_events : "상태 이력"

    tenants {
        int id PK
        varchar name
        boolean is_active
    }
    client_companies {
        int id PK
        int tenant_id FK
        varchar name
        varchar business_no "사업자번호 마스킹 대상"
    }
    users {
        int id PK
        int tenant_id FK
        int client_company_id FK "client 전용"
        varchar email
        varchar hashed_password
        varchar role "client/staff/admin"
    }
    receipts {
        int id PK
        int tenant_id FK
        int client_company_id FK
        int uploaded_by FK
        int reviewed_by FK "검토 세무사"
        varchar file_hash "tenant 내 UNIQUE"
        date transaction_date
        json parsed_data
        varchar status "PENDING~APPROVED"
        varchar account_code
        boolean duplicate_suspect
    }
    receipt_comments {
        int id PK
        int receipt_id FK
        int author_id FK
        text body
    }
    tax_invoices {
        int id PK
        int tenant_id FK
        int client_company_id FK
        int uploaded_by FK
        varchar direction "SALE/PURCHASE"
        varchar approval_no
        date issue_date
        int supply_value_krw
        int vat_krw
    }
    filing_deadlines {
        int id PK
        int tenant_id FK
        int client_company_id FK
        varchar tax_type
        int fiscal_year
        date due_date
        varchar status "pending/completed/overdue"
    }
    audit_events {
        int id PK
        int tenant_id FK
        int actor_user_id FK
        int receipt_id FK
        varchar event_type
        json payload
    }
```

> [!NOTE]
> `audit_events`는 모든 상태 전이와 AI 판단 이력을 남기는 **삭제 금지** 테이블입니다. `receipts`는 `(tenant_id, file_hash)` 복합 UNIQUE로 동일 파일 중복 처리를 막습니다.
> 자동화 5종을 위해 `card_transactions`(카드내역), `account_rules`(계정과목 학습 규칙), `bank_transactions`(통장 거래), `monthly_closings`(월마감 체크리스트) 테이블이 마이그레이션 0009~0012로 추가되었습니다.

<br/>

---

## 🔀 LangGraph 워크플로우 (6노드)

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

> [!NOTE]
> **Graceful Degradation**: Gemini API 장애 → `confidence=0.0` fallback → `requires_human=True` → 세무사 판단

<br/>

---

## 💡 만들면서 한 선택들

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

<br/>

---

## 🚀 로컬 개발 환경 설정

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

<br/>

---

## 🧪 테스트

```bash
# 전체 테스트 (240여 개)
PYTHONPATH=src pytest

# 특정 모듈
PYTHONPATH=src pytest tests/test_celery.py -v
PYTHONPATH=src pytest tests/test_vision.py -v
PYTHONPATH=src pytest tests/test_rag.py -v
```

주요 테스트 파일 (총 32개 파일, 240여 개 테스트):

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
| test_journal.py | 12 | 분개 차/대변 균형, 공제/불공제, CSV export |
| test_reconciliation.py | 10 | 삼중 대사 그리디 매칭 |
| test_account_rules.py | 6 | 거래처 규칙 우선순위·학습 |
| test_missing_evidence.py | 5 | 카드↔영수증 누락 매칭 |
| test_monthly_closing.py | 5 | 월마감 단계 템플릿·진행률 |
| 그 외 | 그 외 | explanation, batch, comments, sse, portal, statements, law_open_data 등 |

<br/>

---

## 🔌 API 엔드포인트

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
| POST | /api/v1/statements/upload | 카드사 엑셀 카드내역 import |
| GET | /api/v1/journal/entries | 분개(전표) 미리보기 |
| GET | /api/v1/journal/export.csv | 회계프로그램용 일반전표 CSV |
| GET / POST / DELETE | /api/v1/account-rules | 거래처별 계정과목 규칙 |
| POST | /api/v1/bank/upload | 통장 거래내역 import |
| GET | /api/v1/bank/reconciliation | 삼중 대사 결과 |
| GET | /api/v1/missing-evidence | 누락 증빙 목록 + 요청 문구 |
| POST / GET | /api/v1/monthly-closings | 월마감 체크리스트 |
| GET | /api/v1/monthly-reports | 월간 정산 지표 |
| GET | /api/v1/portal/dashboard | 고객사 대시보드 (client 전용) |
| GET | /healthz | 헬스체크 |

<br/>

---

## 📦 배포 (Render)

`render.yaml`에 API 서버와 Celery Worker 두 서비스가 정의되어 있습니다.

필요한 환경 변수:
- `DATABASE_URL` — PostgreSQL 연결 문자열
- `REDIS_URL` — Redis 연결 문자열
- `GEMINI_API_KEY` — Google AI Studio API 키
- `QDRANT_URL` — Qdrant 클라우드 또는 자체 호스팅 URL
- `FRONTEND_URL` — Next.js 배포 URL (CORS 허용)

<br/>

---

## 🗂 Phase별 구현 내용

| Phase | 내용 |
|-------|------|
| 0 | src layout, Docker Compose, FastAPI, SQLAlchemy, Alembic, structlog |
| 1 | JWT 인증, bcrypt, DB 모델 5개, magic bytes 검증, 감사 로그 |
| 2 | LangGraph 6노드 워크플로우, HITL interrupt/resume, Decimal VAT |
| 3 | LawChunk, Gemini Embedding, Qdrant, 거래일 기준 법령 검색 |
| 4 | Gemini Vision structured output, Pillow 품질 체크, risk_flags |
| 5 | Celery + Redis 분산 락, acks_late idempotency |
| 6 | Next.js UI, CORS, render.yaml, README |
| 7 | 세금계산서 관리, 부가세 집계, 리스크 스코어링, 신고 기한, 월간 리포트, 고객 포털 |
| 8 | 카드내역 import + 계정과목 분류, 반복 업무 자동화 5종(분개·규칙학습·삼중대사·누락증빙·월마감), 다크 셸 프론트엔드 |

<br/>

> [!TIP]
> 각 Phase별 상세 학습 노트가 `docs/LEARNING_NOTES/`에 있습니다. 면접 질문 목록과 설계 결정 이유가 포함되어 있습니다.

<br/>

---

<div align="center">

**Tax-Copilot** · 1인 개발 · 세무사를 위한 AI 영수증 검토 시스템

</div>

# Tax-Copilot 구현 요약

> 2026-05-25 기준 — FEATURES.md에 정의된 포트폴리오 임팩트 순서대로 구현한 내역

---

## 개요

이 세션에서 Tax-Copilot 백엔드의 핵심 기능 7개를 추가했다. 시작 시 테스트가 28개였고, 완료 시점에 138개다. 모든 기능은 TDD(실패 테스트 → 구현 → 통과) 방식으로 개발했으며 pre-commit 훅(ruff, mypy, detect-secrets)을 통과한 상태로 main에 머지했다.

---

## 구현된 기능 목록

### 1. 의미 기반 중복 영수증 감지

**커밋:** `feat(agents): add duplicate_check_node` 외 4개

**무엇이 달라졌나**

LangGraph 그래프에 `duplicate_check_node`가 추가되었다. 영수증이 업로드될 때 merchant 이름과 금액을 기준으로 최근 30일 내 동일 tenant의 영수증과 비교한다. 단순 문자열 동일 비교가 아니라 `rapidfuzz.fuzz.partial_ratio >= 80`을 사용하기 때문에 "스타벅스"와 "스타벅스강남점"처럼 상호명이 부분 일치하는 경우도 잡아낸다.

**새 파일**
- `src/tax_copilot/agents/nodes/duplicate_check.py` — LangGraph 노드
- `alembic/versions/0003_add_duplicate_suspect.py` — DB 컬럼 추가

**변경 파일**
- `src/tax_copilot/agents/graph.py` — 노드 연결: `intake → duplicate_check → build_retrieval_query`
- `src/tax_copilot/infra/db/models/receipt.py` — `duplicate_suspect`, `duplicate_receipt_ids` 컬럼 추가
- `src/tax_copilot/workers/tasks/receipts.py` — 워커에서 중복 결과 저장
- `src/tax_copilot/schemas/receipts.py` — API 응답에 중복 필드 노출

**효과**
- 중복 가능성 있는 영수증이 `duplicate_suspect=True`로 표시된다
- 세무사가 검토 화면에서 의심 영수증을 즉시 식별 가능

---

### 2. VAT 집계 API

**커밋:** `feat(vat): add VAT aggregation API`

**무엇이 달라졌나**

`GET /api/v1/vat/summary?client_company_id=X&from_date=Y&to_date=Z` 엔드포인트가 생겼다. 기간 내 승인된 영수증의 VAT 공제 가능/불가 금액을 집계하고, 계정과목별로 분류한다.

**새 파일**
- `src/tax_copilot/core/tax/aggregation.py` — 순수 도메인 함수 (ORM 없음)
- `src/tax_copilot/api/v1/vat.py` — API 라우터

**효과**
- 부가세 신고서 작성에 필요한 공제 가능 매입세액을 한 번의 API 호출로 얻을 수 있다
- 핵심 계산 로직이 `core/`에 분리되어 있어 DB 없이도 단위 테스트 가능

---

### 3. 세무 감사 리스크 점수 API

**커밋:** `feat(risk): add tax audit risk scoring API`

**무엇이 달라졌나**

`GET /api/v1/risk/score?client_company_id=X&from_date=Y&to_date=Z`가 0~100 점수를 반환한다. 4가지 지표로 계산한다.

| 지표 | 최대 기여 |
|---|---|
| 접대비 비율 | 40점 |
| 간이영수증 비율 | 30점 |
| 리스크 플래그 비율 | 20점 |
| 중복 의심 비율 | 10점 |

**새 파일**
- `src/tax_copilot/core/tax/risk_scoring.py` — 점수 계산 함수
- `src/tax_copilot/api/v1/risk.py` — API 라우터

**효과**
- 세무사가 고객사별로 감사 위험도를 수치로 확인할 수 있다
- 포트폴리오 시연 시 "AI가 리스크를 정량화한다"는 포인트를 직접 보여줄 수 있다

---

### 4. 배치 업로드

**커밋:** `feat(receipts): add batch upload endpoint`

**무엇이 달라졌나**

`POST /api/v1/receipts/batch`로 최대 20개 파일을 한 번에 업로드할 수 있다. 파일별로 독립 처리되므로 일부 파일이 중복이거나 유효하지 않아도 나머지는 정상 처리된다. 응답에는 각 파일의 `queued/skipped/error` 상태가 포함된다.

**변경 파일**
- `src/tax_copilot/api/v1/receipts.py` — 배치 엔드포인트 추가
- `src/tax_copilot/schemas/receipts.py` — `BatchReceiptResult`, `BatchUploadResponse` 추가
- `alembic/versions/0004_add_batch_id.py` — `batch_id` 컬럼 추가

**효과**
- 월말 대량 영수증 처리 시나리오를 단일 API 호출로 처리 가능
- Celery 디스패치는 DB 커밋 이후에 수행되므로 트랜잭션 안전성 보장

---

### 5. SSE 실시간 상태 스트리밍

**커밋:** `feat(receipts): add SSE endpoint`

**무엇이 달라졌나**

`GET /api/v1/receipts/{id}/events`가 Server-Sent Events 스트림을 반환한다. 클라이언트는 연결을 유지하면서 영수증 처리 상태(`PENDING → PROCESSING → APPROVED/NEEDS_REVIEW`)를 실시간으로 수신한다. 최대 2분(120초) 후 또는 터미널 상태 도달 시 스트림이 닫힌다.

**변경 파일**
- `src/tax_copilot/api/v1/receipts.py` — `StreamingResponse` 기반 SSE 제너레이터 추가

**효과**
- 업로드 후 "처리 중" 폴링 없이 UI가 완료 시점을 정확히 알 수 있다
- Redis pub/sub 없이 DB 폴링으로 구현 — 포트폴리오 규모에 적합

---

### 6. 신고 기한 관리 API

**커밋:** `feat(deadlines): add filing deadline management API`

**무엇이 달라졌나**

세무 신고 기한을 DB에 저장하고 관리하는 3개 엔드포인트가 추가되었다.

- `GET /api/v1/deadlines` — 기한 목록 조회 (필터 지원)
- `POST /api/v1/deadlines/generate` — 연도별 기한 자동 생성 (멱등성 보장)
- `POST /api/v1/deadlines/{id}/complete` — 기한 완료 처리

법인세, 부가세 1/2기, 종합소득세 등 6가지 신고 기한이 연도 입력만으로 자동 생성된다.

**새 파일**
- `src/tax_copilot/core/tax/deadlines.py` — 기한 계산 함수
- `src/tax_copilot/infra/db/models/filing_deadline.py` — 모델
- `src/tax_copilot/api/v1/deadlines.py` — API 라우터
- `alembic/versions/0005_add_filing_deadlines.py` — 테이블 생성

**효과**
- 세무사가 고객사별 신고 기한을 놓치지 않도록 관리 가능
- 기한 자동 생성으로 연간 반복 작업을 API 한 번으로 처리

---

### 7. 판단 근거 추적성 (Explainability)

**커밋:** `feat(receipts): add explanation endpoint`

**무엇이 달라졌나**

`GET /api/v1/receipts/{id}/explanation`이 영수증 한 건에 대한 AI 판단 근거 전체를 반환한다. 포함 내용:

- `decision` — VAT 공제 가능 여부, 계정과목, 신뢰도, 사용된 프롬프트/모델 버전
- `citations` — 판단 근거가 된 세법 조항 (법령명, 조항번호, 유효기간, 인용문)
- `risk_flags` — 감지된 리스크 플래그 목록
- `audit_trail` — 해당 영수증의 모든 감사 이벤트 (업로드, 계정과목 수정 등)

**새 파일**
- `src/tax_copilot/schemas/explanation.py` — 응답 스키마

**변경 파일**
- `src/tax_copilot/api/v1/receipts.py` — 엔드포인트 추가

**효과**
- "왜 이 영수증이 부가세 공제 불가인가?"를 법령 근거와 함께 설명 가능
- 세무 감사 시 AI 판단의 추적 가능성(traceability) 확보

---

### 8. 고객사 포털 — client role 접근 제어

**커밋:** `feat(auth): add client role enforcement`

**무엇이 달라졌나**

JWT에 `client_company_id` 클레임이 추가되었다. role이 `client`인 사용자가 영수증 목록이나 개별 영수증을 조회할 때, 자신의 `client_company_id`에 해당하는 영수증만 볼 수 있도록 DB 쿼리에 필터가 자동 적용된다. `staff`/`admin`은 기존처럼 tenant 전체를 조회한다.

**새 파일**
- `alembic/versions/0006_add_user_client_company_id.py` — users 테이블에 컬럼 추가

**변경 파일**
- `src/tax_copilot/infra/db/models/user.py` — `client_company_id` 컬럼 추가
- `src/tax_copilot/auth/jwt.py` — 토큰 생성 시 `client_company_id` 포함
- `src/tax_copilot/api/deps.py` — `CurrentUser.client_company_id` 추가
- `src/tax_copilot/api/v1/receipts.py` — 목록/단건 조회에 role 기반 필터 적용

**효과**
- 고객 회사 직원이 자신의 영수증만 접근 가능 — 멀티테넌트 보안 강화
- 코드 변경 없이 role 필드만으로 세무사/고객 구분 처리

---

## 수치로 보는 변화

| 항목 | 세션 시작 | 세션 완료 |
|---|---|---|
| 테스트 수 | 28 | 138 |
| API 엔드포인트 수 | ~6 | ~18 |
| Alembic 마이그레이션 | 0002 | 0006 |
| 핵심 도메인 모듈 (`core/`) | 2 | 5 |
| LangGraph 노드 | 없음 | `duplicate_check_node` 추가 |

---

## 아키텍처 원칙 준수

모든 구현에서 다음 원칙을 유지했다.

- **`core/` 격리** — `aggregate_vat`, `score_risk`, `generate_annual_deadlines`, `duplicate_check_node` 계산 로직이 모두 외부 라이브러리 없는 순수 함수 또는 표준 라이브러리만 사용
- **TDD** — 각 기능마다 실패 테스트 먼저 작성 후 구현
- **Conventional Commits** — 모든 커밋이 `feat(scope):` 형식
- **pre-commit 통과** — ruff, ruff-format, mypy, detect-secrets 모두 통과

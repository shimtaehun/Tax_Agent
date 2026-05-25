# 경비 계정과목 자동 분류 — 설계 스펙

Date: 2026-05-24
Status: Approved

---

## 요약

영수증 AI 판단 시 계정과목 대분류(15종)를 자동 분류한다.
`audit_prepare_node`의 기존 LLM 호출에 통합해 추가 API 비용 없이 구현한다.
세무사가 검토 화면에서 확인·수정할 수 있고, JSON API로 결과를 제공한다.

---

## 목표

- `audit_prepare_node` 한 번의 LLM 호출로 판단 초안 + 계정과목 동시 반환
- Receipt DB에 `account_code` 저장
- 검토 API 응답에 계정과목 포함
- 세무사가 계정과목을 수정 확정할 수 있는 PATCH 엔드포인트 제공
- 불확실한 케이스는 `미분류`로 저장 (HITL 강제 없음)

---

## 계정과목 목록 (AccountCode Literal)

```
복리후생비, 접대비, 소모품비, 여비교통비, 통신비,
광고선전비, 수선비, 임차료, 교육훈련비, 도서인쇄비,
회의비, 세금과공과, 보험료, 외주용역비, 미분류
```

선정 근거: `docs/adr/0007-account-code-taxonomy.md` 참조.

---

## 변경 파일 목록

### 1. `src/tax_copilot/core/tax/schemas.py`

`AccountCode` Literal 타입 정의 추가.
`TaxDecision`에 두 필드 추가:
- `account_code: AccountCode` — 기본값 `"미분류"`
- `account_code_reason: str | None` — 분류 근거 한 줄, 기본값 `None`

### 2. `src/tax_copilot/infra/db/models/receipt.py`

Receipt 모델에 컬럼 추가:
- `account_code: Mapped[str | None]` — nullable, DB 저장용

### 3. `alembic/versions/0002_add_account_code.py`

`receipts` 테이블에 `account_code VARCHAR(20) NULL` 컬럼 추가 마이그레이션.

### 4. `src/tax_copilot/agents/nodes/audit_prepare.py`

LLM 프롬프트 끝에 계정과목 분류 지시 추가.
structured output 스키마에 `account_code`, `account_code_reason` 포함.

### 5. `src/tax_copilot/agents/nodes/save_result.py`

`final_decision`에서 `account_code` 읽어 `Receipt.account_code`에 저장.

### 6. `src/tax_copilot/schemas/receipts.py`

`ReceiptStatusResponse`에 `account_code`, `account_code_reason` 필드 추가.

### 7. `src/tax_copilot/api/v1/receipts.py`

`GET /v1/receipts/{id}` 응답에 두 필드 포함.

### 8. `src/tax_copilot/api/v1/reviews.py`

검토 대기 목록·상세 응답에 `account_code` 포함.
`PATCH /v1/receipts/{id}/account-code` 엔드포인트 추가:
- body: `{ "account_code": "접대비" }`
- 15종 외 값은 400 반환
- 변경 시 `audit_events`에 기록

### 9. `src/tax_copilot/schemas/reviews.py`

`ReviewDetailResponse`에 `account_code`, `account_code_reason` 추가.

---

## 데이터 흐름

```
영수증 업로드
  → Celery 태스크
    → audit_prepare_node (LLM)
        입력: ParsedReceipt + 관련 법령
        출력: TaxDecision { vat_creditable, risk_flags, account_code, account_code_reason, ... }
    → save_result_node
        Receipt.account_code ← TaxDecision.account_code 저장
  → 세무사 검토 화면
      GET /v1/reviews/{id}  →  account_code 표시
      PATCH /v1/receipts/{id}/account-code  →  세무사 수정 확정
```

---

## 에러 처리

| 케이스 | 처리 |
|--------|------|
| LLM이 15종 외 값 반환 | Pydantic ValidationError → `미분류`로 fallback |
| PATCH 시 유효하지 않은 account_code | HTTP 400 |
| save_result_node에서 account_code 없음 | `None`으로 저장, 에러 없음 |

---

## 테스트 전략

| 테스트 파일 | 케이스 |
|------------|--------|
| `tests/test_vision.py` | `TaxDecision`에 `account_code` 포함 여부, Literal 외 값 ValidationError |
| `tests/test_graph.py` | `audit_prepare_node` mock에 `account_code` 추가 |
| `tests/test_validation.py` | PATCH API 유효/무효 계정과목 |

---

## 제외 범위 (이 스펙에서 다루지 않음)

- 소분류 (여비교통비 → 국내출장/해외출장 등)
- 업무용/비업무용 구분
- 접대비 한도 누계 계산
- CSV export
- 더존 포맷 매핑

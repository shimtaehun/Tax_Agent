# 의미 기반 중복 영수증 감지 — 설계 스펙

Date: 2026-05-24
Status: Approved

---

## 요약

동일 영수증을 다시 촬영해 재업로드한 경우(파일 해시 다름)를 감지한다.
`intake_node` 직후 `duplicate_check_node`를 삽입해, 파싱 결과 기준 의심 중복을 탐지하고
DB에 저장한다. HITL 강제 없음 — 세무사가 검토 화면에서 확인 후 직접 판단한다.

---

## 목표

- OCR 신뢰도 ≥ 0.75인 경우에만 중복 감지 실행
- (가맹점명 유사 + 금액 동일) 기준으로 의심 중복 탐지
- Receipt DB에 `duplicate_suspect`, `duplicate_receipt_ids` 저장
- API 응답에 포함 (세무사 확인용)
- 신규 업로드 시점에만 체크 (소급 스캔 없음)

---

## 매칭 로직

```
1. extraction_confidence < 0.75 → 통과 (OCR 불확실, 감지 생략)
2. DB 조회: 동일 tenant + 동일 total_amount_krw + APPROVED/NEEDS_REVIEW 상태 영수증 (현재 receipt 제외)
3. rapidfuzz.fuzz.ratio(current_merchant, candidate_merchant) >= 80 이면 의심 중복
4. 해당 receipt_id 목록 → state에 저장
```

merchant_name이 None이면 중복 감지 생략.

---

## LangGraph 워크플로우 변경

```
image_quality_node
  → intake_node
  → duplicate_check_node   ← 신규
  → rag_node
  → calculation_node
  → audit_prepare_node
  → (human_review_node | save_result_node)
```

---

## 변경 파일 목록

### 1. `src/tax_copilot/agents/state.py`

`AgentState`에 필드 추가:
- `duplicate_suspect: bool` — 기본값 `False`
- `duplicate_receipt_ids: list[int]` — 기본값 `[]`

### 2. `src/tax_copilot/agents/nodes/duplicate_check.py` (신규)

```python
async def duplicate_check_node(state: AgentState) -> dict:
    ...
```

- AsyncSession으로 DB 조회 (infra/database.py AsyncSessionLocal 사용)
- rapidfuzz.fuzz.ratio >= 80 기준
- 결과: `{"duplicate_suspect": bool, "duplicate_receipt_ids": [...]}`

### 3. `src/tax_copilot/agents/graph.py`

`intake_node` → `duplicate_check_node` → `rag_node` 순서로 엣지 수정.

### 4. `src/tax_copilot/infra/db/models/receipt.py`

컬럼 추가:
- `duplicate_suspect: Mapped[bool]` — default False, nullable=False
- `duplicate_receipt_ids: Mapped[list | None]` — JSON, nullable=True

### 5. `alembic/versions/0003_add_duplicate_suspect.py`

```sql
ALTER TABLE receipts ADD COLUMN duplicate_suspect BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE receipts ADD COLUMN duplicate_receipt_ids JSON NULL;
```

### 6. `src/tax_copilot/workers/tasks/receipts.py`

`_run_workflow`의 DB 저장 블록에 추가:
```python
receipt.duplicate_suspect = final_state.get("duplicate_suspect", False)
receipt.duplicate_receipt_ids = final_state.get("duplicate_receipt_ids") or []
```

### 7. `src/tax_copilot/schemas/receipts.py`

`ReceiptStatusResponse`에 추가:
- `duplicate_suspect: bool = False`
- `duplicate_receipt_ids: list[int] = []`

### 8. `src/tax_copilot/api/v1/receipts.py`

`_to_status_response`에 두 필드 추가.

---

## 데이터 흐름

```
영수증 업로드
  → intake_node (ParsedReceipt 추출)
  → duplicate_check_node
      confidence < 0.75 → 통과
      merchant_name is None → 통과
      amount 같은 기존 영수증 조회
      rapidfuzz ratio >= 80 → duplicate_suspect=True, ids=[...]
  → rag_node / audit_prepare_node / save_result_node
      Receipt.duplicate_suspect, receipt.duplicate_receipt_ids 저장
  → GET /v1/receipts/{id}
      duplicate_suspect, duplicate_receipt_ids 포함 응답
```

---

## 에러 처리

| 케이스 | 처리 |
|--------|------|
| DB 조회 실패 | 예외 발생 시 `duplicate_suspect=False`로 통과, 에러 로그 |
| merchant_name None | 중복 감지 생략, 통과 |
| rapidfuzz 미설치 | ImportError → requirements에 추가 |
| confidence < 0.75 | 감지 생략, 통과 |

---

## 테스트 전략

| 테스트 파일 | 케이스 |
|------------|--------|
| `tests/test_vision.py` | `duplicate_check_node`: 동일 금액+유사 이름 → suspect=True, 다른 금액 → False, confidence 낮음 → 통과 |
| `tests/test_vision.py` | AgentState에 `duplicate_suspect`, `duplicate_receipt_ids` 포함 여부 |

---

## 제외 범위

- 중복 의심 시 HITL 강제 없음
- 전체 영수증 소급 스캔 없음
- `duplicate_receipt_ids`의 상세 조회 전용 엔드포인트 없음
- 날짜 기반 추가 필터링 없음 (금액+이름으로 충분)

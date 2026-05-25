# Phase 4 완료 보고서 — Gemini Vision & 구조화 출력

완료일: 2026-05-24

## 목표

영수증 이미지에서 실제 정보를 추출하는 Vision 파이프라인을 구현한다.
- `image_quality_node`: 파일 크기 체크 → Pillow 디코드 체크로 강화
- `intake_node`: mock → Gemini Vision structured output으로 교체
- 도메인 스키마 (`ParsedReceipt`, `TaxDecision`) core 레이어에 확정
- `audit_prepare_node`: evidence_type 기반 rule + risk_flags 추가

---

## 구현한 컴포넌트

### ParsedReceipt 스키마 (`src/tax_copilot/core/receipts/schemas.py`)
- `EvidenceType` Literal: tax_invoice, invoice, credit_card_slip, cash_receipt, simplified_receipt, unknown
- `field_validator`: ISO 날짜 문자열 → `date` 자동 변환, "10,000원" → `int` 자동 변환
- `model_dump(mode="json")`: AgentState에 넣을 수 있는 JSON-serializable dict 반환

### TaxDecision 스키마 (`src/tax_copilot/core/tax/schemas.py`)
- `vat_creditable`, `expense_deductible`, `account_title`: 세무 판단 3축
- `risk_flags`, `citations`, `requires_human_review`: 감사 추적용
- `human_approved`, `human_comment`: resume 후 세무사 결정 저장

### Gemini Vision 어댑터 (`src/tax_copilot/infra/gemini/vision.py`)
- `extract_receipt_fields(image_bytes, mime_type) -> ParsedReceipt`
- `gemini-2.0-flash` + structured output (`response_mime_type="application/json"`, `response_schema`)
- `_GeminiReceiptSchema`: date/time을 str로 표현 (Gemini 호환), `_to_parsed_receipt()`로 변환

### image_quality_node 보강 (`src/tax_copilot/agents/nodes/image_quality.py`)
- Phase 2: 파일 크기 체크만
- Phase 4: 파일 크기 + Pillow `Image.verify()` + 최소 해상도 (64×64) 체크
- PDF는 Pillow 체크 건너뜀 (이미지 형식이 아님)
- 비용 이유로 Gemini Vision을 품질 체크에 사용하지 않음

### intake_node 교체 (`src/tax_copilot/agents/nodes/intake.py`)
- Phase 2: 하드코딩된 mock 데이터
- Phase 4: Gemini Vision 호출, API 키 없거나 실패 → confidence=0.0 fallback
- fallback 시 `law_as_of_date = date.today()` (거래일 없음)
- fallback → audit_prepare에서 `requires_human=True` → HITL 경로

### audit_prepare_node 업그레이드 (`src/tax_copilot/agents/nodes/audit_prepare.py`)
- evidence_type별 VAT 공제 가능 여부 자동 판단 (`_VAT_CREDITABLE_BY_EVIDENCE`)
- risk_flags 자동 생성: `simplified_receipt_over_30k`, `missing_transaction_date`, `missing_business_no_on_tax_invoice`
- risk_flags 있으면 자동 판단도 HITL로 격상

---

## 설계 결정

### Gemini Vision을 품질 체크에 쓰지 않은 이유

| 체크 방법 | 비용 | 속도 | 역할 |
|----------|-----|------|------|
| os.path.getsize | 0 | 즉시 | 파일 존재, 크기 |
| Pillow verify | CPU만 | 빠름 | 손상 파일, 해상도 |
| Gemini Vision | API 비용 | 느림 | 실제 영수증 파싱 |

Gemini는 intake_node에서 **딱 한 번만** 호출. 품질 체크에 별도로 쓰면 요청이 2배가 됨.

### audit_prepare에 Gemini LLM을 붙이지 않은 이유

RAG 품질 평가 없이 LLM 판단을 붙이면 안 됨. 법령 데이터가 5개 샘플인 현재 단계에서 LLM이 잘못된 법령을 참조할 수 있음. Rule-based가 법률에 명시된 규칙을 정확히 구현하므로 현 단계에서 충분.

---

## 테스트 결과

`tests/test_vision.py` — 22개 전체 통과:

| 클래스 | 테스트 수 | 내용 |
|--------|---------|------|
| `TestParsedReceiptSchema` | 6 | 스키마 검증, 타입 변환, JSON 직렬화 |
| `TestImageQualityNode` | 6 | 유효 JPEG, 크기 미달, 손상 파일, 해상도 미달, PDF |
| `TestIntakeNode` | 3 | API 없을 때 fallback, mock 성공, 날짜 없을 때 오늘 날짜 |
| `TestAuditPrepareNode` | 7 | 법령 없음, 신뢰도 낮음, 신용카드 VAT 공제, 계산서, 간이영수증, 거래일 없음, 인용 목록 |

전체 테스트 스위트 71개 통과.

### test_graph.py fixture 수정

`valid_file` fixture가 가짜 JPEG(magic bytes만 있는 파일)를 생성했는데, Pillow 디코드 체크가 추가되면서 실패. Pillow로 실제 200×200 JPEG를 생성하도록 수정.

---

## Phase 5 예고

- Celery 비동기 작업 dispatch
- Redis 분산 lock으로 중복 처리 방지
- `acks_late=True` + idempotency: worker 강제 종료해도 중복 처리 없음
- FastAPI 업로드 엔드포인트 → Celery task로 연결

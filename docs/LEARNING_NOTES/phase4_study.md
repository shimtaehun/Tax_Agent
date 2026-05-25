# Phase 4 학습 노트 — Gemini Vision & 구조화 출력

> 이 파일은 직접 읽으면서 공부하는 용도로 작성되었습니다.
> Gemini Vision, Pillow, Pydantic structured output의 핵심 개념을 다룹니다.

---

## 1. Gemini Vision이란?

### 기존 LLM과의 차이

기존 LLM: 텍스트 입력 → 텍스트 출력
Gemini Vision: **이미지 + 텍스트 입력** → 텍스트 출력

```python
# 이미지와 텍스트 프롬프트를 함께 전달
image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=["이 영수증에서 금액을 추출해줘", image_part],
)
```

### 영수증에 Vision이 필요한 이유

영수증 파일은 이미지입니다. 상점명, 금액, 날짜 등의 정보가 텍스트가 아닌 **이미지로 인쇄**되어 있습니다. 이를 읽으려면 OCR(광학 문자 인식) 또는 Vision 모델이 필요합니다.

Gemini Vision은 OCR 기능을 내장하고 있어서 영수증 이미지를 직접 입력받아 구조화된 정보를 추출할 수 있습니다.

---

## 2. Structured Output (구조화된 출력)

### 문제: LLM 출력은 형식이 자유롭다

```
"상호명은 스타벅스이고, 금액은 5,500원입니다. 날짜는 2024년 6월 15일..."
```

이 텍스트에서 금액을 파싱하려면 정규식이 필요합니다. 형식이 응답마다 다를 수 있습니다.

### 해결: response_schema로 JSON 출력 강제

```python
# src/tax_copilot/infra/gemini/vision.py
response = client.models.generate_content(
    model=_MODEL,
    contents=[_PROMPT, image_part],
    config=genai_types.GenerateContentConfig(
        response_mime_type="application/json",   # JSON 형식으로 출력
        response_schema=_GeminiReceiptSchema,    # Pydantic 스키마로 형식 고정
    ),
)

raw: _GeminiReceiptSchema = response.parsed  # 자동으로 Pydantic 객체로 변환
```

`response_schema`에 Pydantic 모델을 지정하면 Gemini가 항상 그 형식으로 JSON을 출력합니다. `response.parsed`로 바로 Pydantic 객체를 얻을 수 있습니다.

### 왜 별도 `_GeminiReceiptSchema`를 만드는가?

`ParsedReceipt`는 `date`, `time` 타입을 사용합니다. Gemini structured output은 Python 기본 타입만 지원합니다. 그래서:

- `ParsedReceipt` (도메인 모델): `date`, `time` 타입 사용
- `_GeminiReceiptSchema` (Gemini용): `str | None` 사용, 변환은 `_to_parsed_receipt()`가 담당

```python
class _GeminiReceiptSchema(BaseModel):
    transaction_date: str | None = None   # "2024-06-15" 문자열
    ...

def _to_parsed_receipt(raw: _GeminiReceiptSchema) -> ParsedReceipt:
    return ParsedReceipt(
        transaction_date=raw.transaction_date,  # ParsedReceipt.field_validator가 파싱
        ...
    )
```

---

## 3. Pydantic field_validator — 입력 자동 변환

```python
# src/tax_copilot/core/receipts/schemas.py
class ParsedReceipt(BaseModel):
    transaction_date: date | None = None

    @field_validator("transaction_date", mode="before")
    @classmethod
    def parse_date(cls, v: object) -> object:
        if isinstance(v, str) and v:
            try:
                return date.fromisoformat(v)  # "2024-06-15" → date(2024, 6, 15)
            except ValueError:
                return None
        return v
```

`mode="before"`: Pydantic이 타입 변환하기 **전에** 실행됩니다. 문자열이 입력되면 먼저 `date`로 변환합니다. 변환 실패 시 `None`을 반환해서 예외가 나지 않도록 합니다.

이 덕분에 Gemini가 `"2024-06-15"` 문자열로 반환해도, `"not-a-date"` 같은 잘못된 값이 와도 모두 처리됩니다.

---

## 4. Pillow — 이미지 품질 결정론적 체크

### 왜 Gemini Vision을 품질 체크에 쓰지 않는가?

Gemini API 호출은 비용이 발생합니다. 완전히 손상된 파일이나 너무 작은 파일을 Gemini에 보낼 필요가 없습니다. Pillow로 먼저 걸러내면 비용을 아낄 수 있습니다.

**단계별 체크 (비용 순으로 낮은 것부터):**
1. 파일 크기 (os.path.getsize) — 가장 빠름, 비용 0
2. Pillow 디코드 체크 — 빠름, CPU만 사용
3. Gemini Vision — 느림, API 비용 발생

Gemini는 intake_node에서 딱 한 번만 호출합니다.

### `Image.verify()` vs `Image.open()`

```python
with Image.open(file_path) as img:
    img.verify()   # 파일 헤더와 구조 검증 (빠름)

# verify() 이후 재오픈 필요!
with Image.open(file_path) as img:
    width, height = img.size
```

`verify()`는 실제 픽셀 데이터를 디코딩하지 않고 파일 구조만 검사합니다. 빠르지만 파일 포인터를 닫아버리기 때문에, 이후에 실제 정보(size 등)를 읽으려면 다시 열어야 합니다.

---

## 5. 적격증빙 종류와 부가세 공제

세금 처리에서 "어떤 종류의 영수증인가"는 매우 중요합니다.

| 증빙 종류 | evidence_type | 부가세 공제 | 비고 |
|----------|--------------|------------|------|
| 세금계산서 | `tax_invoice` | 가능 | 가장 강력한 적격증빙 |
| 계산서 | `invoice` | 불가 | 면세 거래 |
| 신용카드 매출전표 | `credit_card_slip` | 가능 | 사업용 카드 필요 |
| 현금영수증 | `cash_receipt` | 가능 | 사업자 발급 필요 |
| 간이영수증 | `simplified_receipt` | 불가(3만원 초과) | 소액 거래만 인정 |

```python
# src/tax_copilot/agents/nodes/audit_prepare.py
_VAT_CREDITABLE_BY_EVIDENCE = {
    "tax_invoice": True,
    "credit_card_slip": True,
    "cash_receipt": True,
    "invoice": False,
    "simplified_receipt": False,
    "unknown": None,
}
```

`None`은 "판단 불가"를 의미합니다. 세무사가 직접 판단해야 합니다.

---

## 6. Risk Flag — 위험 신호 자동 감지

```python
# src/tax_copilot/agents/nodes/audit_prepare.py
def _build_risk_flags(parsed: dict) -> list[str]:
    flags = []

    # 간이영수증 + 3만원 초과
    if evidence_type == "simplified_receipt" and total > 30000:
        flags.append("simplified_receipt_over_30k")

    # 거래일 없음
    if not parsed.get("transaction_date"):
        flags.append("missing_transaction_date")

    return flags
```

risk_flags가 있으면 자동 판단이라도 HITL로 격상됩니다. 세무사가 직접 확인해야 하는 상황을 자동으로 감지합니다.

**왜 중요한가?** 간이영수증은 건당 3만원 이하만 비용 인정이 됩니다 (법인세법). 이를 놓치면 세무 리스크가 생깁니다.

---

## 7. Graceful Degradation 체인

Gemini API 없거나 실패해도 시스템이 멈추지 않는 전체 흐름:

```
[intake_node]
  ↓ Gemini 실패
  → confidence=0.0 fallback 반환

[retrieval_node]
  ↓ Gemini 임베딩 실패
  → relevant_laws=[] 반환

[audit_prepare_node]
  ↓ laws=[] OR confidence<0.75
  → requires_human=True 설정

[human_review_node]
  → interrupt() 발동
  → 세무사에게 판단 위임
```

어느 단계에서 외부 서비스가 실패해도, 결국 세무사(HITL)가 처리합니다. "AI가 실패하면 사람이 한다"는 원칙이 코드로 구현되어 있습니다.

---

## 8. 이 Phase에서 의도적으로 하지 않은 것

### audit_prepare에 Gemini LLM을 붙이지 않은 이유

설계 문서에는 Phase 4에서 `audit_prepare_node`를 Gemini LLM으로 교체한다고 되어 있습니다. 하지만 현재는 rule-based로 유지했습니다.

이유:
1. **법령 정확도 평가 전에 LLM 판단을 붙이면 안 됩니다.** RAG가 맞는 법령을 가져오는지 먼저 확인해야, LLM이 그 법령을 제대로 해석하는지 평가할 수 있습니다.
2. **Prompt engineering이 필요합니다.** "부가세 공제 가능 여부 판단" 프롬프트는 세무 전문 지식을 담아야 합니다. 잘못된 프롬프트는 잘못된 세무 판단을 낳습니다.
3. **Rule-based가 이미 충분합니다.** 증빙 종류(evidence_type)로 부가세 공제 가능 여부를 판단하는 것은 법률에 명시된 규칙이므로, LLM 없이도 정확합니다.

---

## 핵심 질문 목록 (면접 준비)

1. "Gemini structured output을 사용하면 좋은 점은?"
2. "왜 이미지 품질 체크를 Gemini Vision이 아닌 Pillow로 하나요?"
3. "Pillow의 Image.verify() 후 재오픈이 필요한 이유는?"
4. "evidence_type이 'unknown'일 때 vat_creditable이 None인 이유는?"
5. "간이영수증 3만원 초과가 risk_flag인 이유는? (법률 근거)"
6. "Gemini API 장애가 났을 때 이 시스템은 어떻게 동작하나요?"
7. "ParsedReceipt와 _GeminiReceiptSchema를 분리한 이유는?"
8. "field_validator에 mode='before'를 쓰는 이유는?"

"""Gemini Vision 어댑터 — 영수증 이미지 파싱.

structured output을 사용해 ParsedReceipt를 직접 반환한다.
Gemini API 키 없으면 RuntimeError → 호출부에서 ExternalServiceError로 변환.
"""

from pydantic import BaseModel, Field

from tax_copilot.core.config import settings
from tax_copilot.core.receipts.schemas import EvidenceType, ParsedReceipt

_MODEL = "gemini-2.0-flash"

# Gemini structured output용 스키마 (ParsedReceipt와 동일 구조, json-serializable 타입만)
_PROMPT = """
다음 영수증 이미지에서 정보를 추출하세요.

- merchant_name: 상호명
- merchant_business_no: 사업자등록번호 (형식: 000-00-00000, 없으면 null)
- transaction_date: 거래일 (YYYY-MM-DD 형식, 없으면 null)
- transaction_time: 거래시각 (HH:MM:SS 형식, 없으면 null)
- total_amount_krw: 총 결제금액 (숫자만, 없으면 null)
- supply_value_krw: 공급가액 (부가세 제외, 없으면 null)
- vat_amount_krw: 부가가치세액 (없으면 null)
- items: 구매 항목 목록 (문자열 배열)
- payment_method: 결제수단 (예: 신용카드, 현금)
- evidence_type: 증빙 종류
  (tax_invoice/invoice/credit_card_slip/cash_receipt/simplified_receipt/unknown)
- raw_ocr_text: 이미지에서 읽은 원문 텍스트 전체
- extraction_confidence: 추출 신뢰도 0.0~1.0 (명확히 보이면 0.9 이상)

금액은 쉼표나 '원' 제거 후 정수로 반환하세요.
"""


class _GeminiReceiptSchema(BaseModel):
    """Gemini structured output용 스키마. ParsedReceipt와 동일하지만 date/time을 str로."""

    merchant_name: str | None = None
    merchant_business_no: str | None = None
    transaction_date: str | None = None  # "YYYY-MM-DD"
    transaction_time: str | None = None  # "HH:MM:SS"
    total_amount_krw: int | None = None
    supply_value_krw: int | None = None
    vat_amount_krw: int | None = None
    items: list[str] = Field(default_factory=list)
    payment_method: str | None = None
    evidence_type: str = "unknown"
    raw_ocr_text: str | None = None
    extraction_confidence: float = 0.5


def _get_client():  # type: ignore[return]
    if not settings.gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY 환경 변수가 설정되지 않았습니다.")
    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)


def _to_parsed_receipt(raw: _GeminiReceiptSchema) -> ParsedReceipt:
    """Gemini 응답을 ParsedReceipt로 변환한다."""
    evidence = raw.evidence_type if raw.evidence_type in EvidenceType.__args__ else "unknown"

    return ParsedReceipt(
        merchant_name=raw.merchant_name,
        merchant_business_no=raw.merchant_business_no,
        transaction_date=raw.transaction_date,  # field_validator가 파싱
        transaction_time=raw.transaction_time,
        total_amount_krw=raw.total_amount_krw,
        supply_value_krw=raw.supply_value_krw,
        vat_amount_krw=raw.vat_amount_krw,
        items=raw.items,
        payment_method=raw.payment_method,
        evidence_type=evidence,  # type: ignore[arg-type]
        raw_ocr_text=raw.raw_ocr_text,
        extraction_confidence=max(0.0, min(1.0, raw.extraction_confidence)),
    )


async def extract_receipt_fields(
    image_bytes: bytes, mime_type: str = "image/jpeg"
) -> ParsedReceipt:
    """영수증 이미지에서 구조화된 정보를 추출한다.

    Args:
        image_bytes: 영수증 이미지 bytes
        mime_type: 이미지 MIME 타입 (image/jpeg, image/png, application/pdf)

    Returns:
        ParsedReceipt 인스턴스

    Raises:
        RuntimeError: Gemini API 키 없을 때
        Exception: Gemini API 호출 실패 시
    """
    client = _get_client()

    from google.genai import types as genai_types

    image_part = genai_types.Part.from_bytes(data=image_bytes, mime_type=mime_type)

    response = client.models.generate_content(
        model=_MODEL,
        contents=[_PROMPT, image_part],
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_GeminiReceiptSchema,
        ),
    )

    raw: _GeminiReceiptSchema = response.parsed
    return _to_parsed_receipt(raw)

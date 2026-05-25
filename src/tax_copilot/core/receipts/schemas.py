"""영수증 파싱 결과 도메인 모델.

core/ 레이어이므로 외부 라이브러리 없음 (pydantic, typing, datetime 허용).
"""

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# 적격증빙 종류 — evidence_type은 이 값 중 하나여야 한다
EvidenceType = Literal[
    "tax_invoice",  # 세금계산서 (매입세액 공제 가능)
    "invoice",  # 계산서 (면세)
    "credit_card_slip",  # 신용카드 매출전표
    "cash_receipt",  # 현금영수증
    "simplified_receipt",  # 간이영수증 (3만원 초과 시 비적격)
    "unknown",
]


class ParsedReceipt(BaseModel):
    """Gemini Vision이 영수증 이미지에서 추출한 구조화 데이터."""

    merchant_name: str | None = None
    merchant_business_no: str | None = None  # 사업자등록번호

    transaction_date: date | None = None
    transaction_time: time | None = None

    total_amount_krw: int | None = None
    supply_value_krw: int | None = None  # 공급가액 (부가세 제외)
    vat_amount_krw: int | None = None  # 부가세

    items: list[str] = Field(default_factory=list)
    payment_method: str | None = None  # 신용카드, 현금 등

    evidence_type: EvidenceType = "unknown"
    raw_ocr_text: str | None = None

    extraction_confidence: float = Field(ge=0.0, le=1.0)

    @field_validator("transaction_date", mode="before")
    @classmethod
    def parse_date(cls, v: object) -> object:
        """ISO 문자열도 date로 변환한다."""
        if isinstance(v, str) and v:
            try:
                return date.fromisoformat(v)
            except ValueError:
                return None
        return v

    @field_validator("total_amount_krw", "supply_value_krw", "vat_amount_krw", mode="before")
    @classmethod
    def parse_amount(cls, v: object) -> object:
        """문자열 금액도 int로 변환한다 ('10,000' → 10000)."""
        if isinstance(v, str):
            cleaned = v.replace(",", "").replace("원", "").strip()
            return int(cleaned) if cleaned.isdigit() else None
        return v

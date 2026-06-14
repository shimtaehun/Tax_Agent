from datetime import date

from pydantic import BaseModel


class MissingEvidenceCard(BaseModel):
    card_transaction_id: int
    transaction_date: date | None
    merchant_name: str | None
    amount_krw: int


class MissingEvidenceResponse(BaseModel):
    client_company_id: int
    from_date: date
    to_date: date
    card_count: int
    receipt_count: int
    missing_count: int
    missing_amount_krw: int
    items: list[MissingEvidenceCard]
    # 고객사에 그대로 전달 가능한 요청 문구
    request_message: str

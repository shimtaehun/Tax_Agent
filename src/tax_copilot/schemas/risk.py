from datetime import date

from pydantic import BaseModel


class RiskIndicators(BaseModel):
    entertainment_ratio: float
    simplified_ratio: float
    risk_flag_ratio: float
    duplicate_ratio: float


class RiskScoreResponse(BaseModel):
    client_company_id: int
    from_date: date
    to_date: date
    score: int
    flags: list[str]
    explanation: str
    indicators: RiskIndicators
    total_approved: int
    pending_review_count: int

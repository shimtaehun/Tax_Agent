"""세무 판단 도메인 모델.

core/ 레이어이므로 외부 라이브러리 없음 (pydantic 허용).
"""

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

EvidenceStatus = Literal["valid", "insufficient", "unreadable", "unknown"]

AccountCode = Literal[
    "복리후생비",
    "접대비",
    "소모품비",
    "여비교통비",
    "통신비",
    "광고선전비",
    "수선비",
    "임차료",
    "교육훈련비",
    "도서인쇄비",
    "회의비",
    "세금과공과",
    "보험료",
    "외주용역비",
    "미분류",
]


class Citation(BaseModel):
    """판단 근거로 인용한 법령 chunk."""

    chunk_id: str
    law_name: str
    article_no: str | None = None
    paragraph_no: str | None = None
    effective_from: date
    effective_to: date | None = None
    quoted_text: str


class TaxDecision(BaseModel):
    """세무 판단 결과. audit_prepare_node와 human_review_node가 생성한다."""

    vat_creditable: bool | None = Field(
        default=None,
        description="부가세 매입세액 공제 가능 여부. None은 판단 불가.",
    )
    expense_deductible: bool | None = Field(
        default=None,
        description="법인세/소득세 손금(필요경비) 산입 가능 여부.",
    )
    account_code: AccountCode = Field(
        default="미분류",
        description="경비 계정과목 대분류 (15종).",
    )
    account_code_reason: str | None = Field(
        default=None,
        description="계정과목 분류 근거 한 줄.",
    )

    evidence_type: str = "unknown"
    evidence_status: EvidenceStatus = "unknown"
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    risk_flags: list[str] = Field(default_factory=list)
    citations: list[Citation] = Field(default_factory=list)

    requires_human_review: bool
    review_reason: str | None = None

    # 감사 추적용
    prompt_version: str
    model_name: str
    law_corpus_version: str

    # 계산 결과 포함 (감사 로그용)
    calculation_result: dict[str, object] | None = None

    # 세무사 검토 결과 (resume 후 채워짐)
    human_approved: bool | None = None
    human_comment: str | None = None

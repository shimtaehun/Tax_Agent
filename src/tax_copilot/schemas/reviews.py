from datetime import datetime

from pydantic import BaseModel, model_validator


class ReviewItem(BaseModel):
    """세무사 검토 대기 중인 영수증 항목."""

    receipt_id: int
    original_filename: str
    langgraph_thread_id: str
    created_at: datetime


class ReviewDecision(BaseModel):
    approved: bool
    comment: str | None = None

    @model_validator(mode="after")
    def comment_required_on_reject(self) -> "ReviewDecision":
        if not self.approved and not self.comment:
            raise ValueError("반려 시 검토 의견을 입력해야 합니다.")
        return self


class ReviewResult(BaseModel):
    receipt_id: int
    status: str
    message: str


class ReviewHistoryItem(BaseModel):
    """승인 또는 반려된 영수증 항목."""

    receipt_id: int
    original_filename: str
    status: str
    reviewed_by: int | None
    reviewed_at: datetime | None
    review_comment: str | None
    transaction_date: str | None
    account_code: str | None = None
    created_at: datetime

from datetime import date, datetime

from pydantic import BaseModel


class FilingDeadlineResponse(BaseModel):
    id: int
    client_company_id: int
    tax_type: str
    fiscal_year: int
    due_date: date
    description: str
    status: str
    completed_at: datetime | None
    completed_by: int | None
    created_at: datetime


class DeadlineListResponse(BaseModel):
    items: list[FilingDeadlineResponse]
    total: int


class GenerateDeadlinesRequest(BaseModel):
    client_company_id: int
    fiscal_year: int


class GenerateDeadlinesResponse(BaseModel):
    created_count: int
    skipped_count: int  # 이미 존재하는 항목 (unique 제약으로 건너뜀)

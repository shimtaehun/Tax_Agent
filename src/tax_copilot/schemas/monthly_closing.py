from datetime import datetime

from pydantic import BaseModel


class ClosingStepOut(BaseModel):
    key: str
    label: str
    done: bool
    done_at: str | None = None


class MonthlyClosingCreate(BaseModel):
    client_company_id: int
    year: int
    month: int


class StepUpdateRequest(BaseModel):
    done: bool


class MonthlyClosingOut(BaseModel):
    id: int
    client_company_id: int
    year: int
    month: int
    status: str
    progress: float
    steps: list[ClosingStepOut]
    created_at: datetime


class MonthlyClosingListResponse(BaseModel):
    items: list[MonthlyClosingOut]
    total: int

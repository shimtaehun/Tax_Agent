from datetime import datetime

from pydantic import BaseModel


class CommentResponse(BaseModel):
    id: int
    receipt_id: int
    author_id: int
    body: str
    created_at: datetime


class CommentListResponse(BaseModel):
    items: list[CommentResponse]


class CommentCreateRequest(BaseModel):
    body: str

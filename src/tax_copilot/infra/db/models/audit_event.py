from datetime import datetime

from sqlalchemy import JSON, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from tax_copilot.infra.db.models.base import Base

# 이벤트 타입 상수 — 추가 시 여기에 선언
RECEIPT_UPLOADED = "RECEIPT_UPLOADED"
RECEIPT_PROCESSING_STARTED = "RECEIPT_PROCESSING_STARTED"
AI_EXTRACTION_COMPLETED = "AI_EXTRACTION_COMPLETED"
RAG_SEARCH_COMPLETED = "RAG_SEARCH_COMPLETED"
AI_DECISION_DRAFTED = "AI_DECISION_DRAFTED"
HUMAN_REVIEW_REQUESTED = "HUMAN_REVIEW_REQUESTED"
HUMAN_REVIEW_APPROVED = "HUMAN_REVIEW_APPROVED"
HUMAN_REVIEW_REJECTED = "HUMAN_REVIEW_REJECTED"
RECEIPT_PROCESSING_FAILED = "RECEIPT_PROCESSING_FAILED"
ACCOUNT_CODE_UPDATED = "ACCOUNT_CODE_UPDATED"


class AuditEvent(Base):
    """모든 상태 전이와 판단 이력. 삭제 금지."""

    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    actor_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    receipt_id: Mapped[int | None] = mapped_column(ForeignKey("receipts.id"), nullable=True)

    event_type: Mapped[str] = mapped_column(String(100), index=True)
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

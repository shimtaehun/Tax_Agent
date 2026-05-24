from datetime import date, datetime

from sqlalchemy import JSON, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from tax_copilot.infra.db.models.base import Base

# 처리 상태 상수
STATUS_PENDING = "PENDING"
STATUS_PROCESSING = "PROCESSING"
STATUS_NEEDS_REVIEW = "NEEDS_REVIEW"
STATUS_APPROVED = "APPROVED"
STATUS_REJECTED = "REJECTED"
STATUS_FAILED = "FAILED"


class Receipt(Base):
    """업로드된 영수증 파일과 처리 상태."""

    __tablename__ = "receipts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True)
    client_company_id: Mapped[int] = mapped_column(ForeignKey("client_companies.id"), index=True)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))

    # 파일 정보
    file_path: Mapped[str] = mapped_column(String(500))
    file_hash: Mapped[str] = mapped_column(String(64))
    original_filename: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    file_size_bytes: Mapped[int]

    # 추출된 거래 정보
    transaction_date: Mapped[date | None] = mapped_column(nullable=True)
    parsed_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # 처리 상태
    status: Mapped[str] = mapped_column(String(30), default=STATUS_PENDING, index=True)
    langgraph_thread_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    celery_task_id: Mapped[str | None] = mapped_column(String(150), nullable=True)
    attempt_number: Mapped[int] = mapped_column(default=1)
    error_message: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    # 계정과목 분류 결과
    account_code: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # 중복 감지 결과
    duplicate_suspect: Mapped[bool] = mapped_column(default=False, server_default="false")
    duplicate_receipt_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # 세무사 검토
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(nullable=True)
    review_comment: Mapped[str | None] = mapped_column(String(1000), nullable=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        # tenant 내 동일 파일 중복 처리 방지
        UniqueConstraint("tenant_id", "file_hash", name="uq_receipts_tenant_file_hash"),
    )

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import get_current_user, get_db
from tax_copilot.core.exceptions import DuplicateReceiptError
from tax_copilot.core.receipts.validation import validate_upload
from tax_copilot.infra.db.models.user import User
from tax_copilot.infra.db.repositories.receipts import create_receipt, log_audit_event
from tax_copilot.infra.storage.local import store_receipt

router = APIRouter(prefix="/receipts", tags=["receipts"])


class ReceiptResponse(BaseModel):
    id: int
    status: str
    original_filename: str
    file_size_bytes: int
    created_at: datetime


@router.post("", response_model=ReceiptResponse, status_code=201)
async def upload_receipt(
    file: UploadFile,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ReceiptResponse:
    content = await file.read()
    mime = validate_upload(file.filename or "", content)

    try:
        file_path, file_hash = store_receipt(current_user.tenant_id, content, mime)
    except Exception as e:
        raise DuplicateReceiptError(str(e)) from e

    async with session.begin():
        try:
            receipt = await create_receipt(
                session,
                tenant_id=current_user.tenant_id,
                uploaded_by=current_user.id,
                file_path=file_path,
                file_hash=file_hash,
                original_filename=file.filename or "unknown",
                mime_type=mime,
                file_size_bytes=len(content),
                status="PENDING",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
            await log_audit_event(
                session,
                tenant_id=current_user.tenant_id,
                actor_user_id=current_user.id,
                receipt_id=receipt.id,
                event_type="RECEIPT_UPLOADED",
                payload={"filename": file.filename, "mime_type": mime, "size": len(content)},
            )
        except Exception as e:
            raise DuplicateReceiptError("Receipt with this file already exists for tenant") from e

    return ReceiptResponse(
        id=receipt.id,
        status=receipt.status,
        original_filename=receipt.original_filename,
        file_size_bytes=receipt.file_size_bytes,
        created_at=receipt.created_at,
    )


@router.get("", response_model=list[ReceiptResponse])
async def list_receipts_endpoint(
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ReceiptResponse]:
    from tax_copilot.infra.db.repositories.receipts import list_receipts

    receipts = await list_receipts(session, current_user.tenant_id)
    return [
        ReceiptResponse(
            id=r.id,
            status=r.status,
            original_filename=r.original_filename,
            file_size_bytes=r.file_size_bytes,
            created_at=r.created_at,
        )
        for r in receipts
    ]

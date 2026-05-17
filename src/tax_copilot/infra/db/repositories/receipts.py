from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.infra.db.models.receipt import AuditEvent, Receipt


async def create_receipt(session: AsyncSession, **kwargs: object) -> Receipt:
    receipt = Receipt(**kwargs)
    session.add(receipt)
    await session.flush()
    return receipt


async def get_receipt(session: AsyncSession, receipt_id: int, tenant_id: int) -> Receipt | None:
    result = await session.execute(
        select(Receipt).where(Receipt.id == receipt_id, Receipt.tenant_id == tenant_id)
    )
    return result.scalar_one_or_none()


async def list_receipts(
    session: AsyncSession, tenant_id: int, limit: int = 20, offset: int = 0
) -> list[Receipt]:
    result = await session.execute(
        select(Receipt)
        .where(Receipt.tenant_id == tenant_id)
        .order_by(Receipt.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def log_audit_event(
    session: AsyncSession,
    *,
    tenant_id: int,
    event_type: str,
    payload: dict,
    actor_user_id: int | None = None,
    receipt_id: int | None = None,
) -> AuditEvent:
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        receipt_id=receipt_id,
        event_type=event_type,
        payload=payload,
        created_at=datetime.now(UTC),
    )
    session.add(event)
    await session.flush()
    return event

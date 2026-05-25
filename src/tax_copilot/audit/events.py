from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.infra.db.models.audit_event import AuditEvent


async def record_event(
    db: AsyncSession,
    *,
    tenant_id: int,
    event_type: str,
    payload: dict[str, object],
    actor_user_id: int | None = None,
    receipt_id: int | None = None,
) -> None:
    """audit_events 테이블에 상태 전이 이벤트를 기록한다."""
    event = AuditEvent(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        receipt_id=receipt_id,
        event_type=event_type,
        payload=payload,
    )
    db.add(event)
    # flush만 수행 — commit은 호출자가 담당
    await db.flush()

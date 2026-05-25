"""초기 admin 사용자와 테넌트를 생성하는 seed 스크립트.

사용법:
    python scripts/seed_admin.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from tax_copilot.auth.password import hash_password
from tax_copilot.core.config import settings
from tax_copilot.infra.db.models.client_company import ClientCompany
from tax_copilot.infra.db.models.tenant import Tenant
from tax_copilot.infra.db.models.user import ROLE_ADMIN, User

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
TENANT_NAME = os.getenv("TENANT_NAME", "Tax-Copilot Dev")


async def seed() -> None:
    from sqlalchemy import select

    engine = create_async_engine(settings.database_url)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    async with SessionLocal() as db:
        # 이미 동일한 이름의 tenant가 있으면 skip (멱등 실행 보장)
        existing = await db.execute(select(Tenant).where(Tenant.name == TENANT_NAME))
        tenant = existing.scalar_one_or_none()

        if tenant is None:
            tenant = Tenant(name=TENANT_NAME)
            db.add(tenant)
            await db.flush()

            default_company = ClientCompany(tenant_id=tenant.id, name="기본 고객사")
            db.add(default_company)
            await db.flush()

            admin = User(
                tenant_id=tenant.id,
                email=ADMIN_EMAIL,
                hashed_password=hash_password(ADMIN_PASSWORD),
                role=ROLE_ADMIN,
            )
            db.add(admin)
            await db.commit()
            print(f"생성 완료 — Tenant: {TENANT_NAME} (id={tenant.id}), Admin: {ADMIN_EMAIL}")
        else:
            existing_company = await db.execute(
                select(ClientCompany).where(ClientCompany.tenant_id == tenant.id)
            )
            default_company = existing_company.scalars().first()
            print(f"이미 존재 — Tenant: {TENANT_NAME} (id={tenant.id}), Admin: {ADMIN_EMAIL}")

    print(f"Default company id: {default_company.id if default_company else 'N/A'}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())

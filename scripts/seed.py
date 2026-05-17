"""개발용 시드 데이터: tenant 1개 + admin 유저 1개."""

import asyncio

from sqlalchemy import text

from tax_copilot.core.auth import hash_password
from tax_copilot.infra.database import AsyncSessionLocal, engine
from tax_copilot.infra.db.models import Base, Tenant, User


async def seed() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            result = await session.execute(text("SELECT id FROM tenants WHERE id=1"))
            if result.scalar_one_or_none():
                print("Already seeded.")
                return

            tenant = Tenant(name="테스트 세무법인", is_active=True)
            session.add(tenant)
            await session.flush()

            admin = User(
                tenant_id=tenant.id,
                email="admin@tax.test",
                hashed_password=hash_password("admin1234"),
                role="admin",
                is_active=True,
            )
            session.add(admin)

    print(f"Seeded: tenant_id={tenant.id}, email=admin@tax.test, password=admin1234")


asyncio.run(seed())

"""공유 pytest fixtures."""

import pytest
from httpx import ASGITransport, AsyncClient

from tax_copilot.api.main import app
from tax_copilot.auth.jwt import create_access_token


@pytest.fixture
async def async_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    token = create_access_token(user_id=1, tenant_id=1, role="staff")
    return {"Authorization": f"Bearer {token}"}

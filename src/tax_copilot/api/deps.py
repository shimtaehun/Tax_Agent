from collections.abc import AsyncGenerator
from dataclasses import dataclass

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.auth.jwt import decode_access_token
from tax_copilot.core.exceptions import AuthenticationError
from tax_copilot.infra.database import get_session

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    user_id: int
    tenant_id: int
    role: str
    client_company_id: int | None = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in get_session():
        yield session


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> CurrentUser:
    if credentials is None:
        raise AuthenticationError("인증 토큰이 없습니다.")
    payload = decode_access_token(credentials.credentials)
    try:
        raw_cid = payload.get("client_company_id")
        return CurrentUser(
            user_id=int(str(payload["sub"])),
            tenant_id=int(str(payload["tenant_id"])),
            role=str(payload["role"]),
            client_company_id=int(str(raw_cid)) if raw_cid is not None else None,
        )
    except (KeyError, ValueError) as exc:
        raise AuthenticationError("토큰 페이로드가 올바르지 않습니다.") from exc

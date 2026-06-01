from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import get_db
from tax_copilot.auth.jwt import create_access_token
from tax_copilot.auth.password import verify_password
from tax_copilot.core.exceptions import AuthenticationError
from tax_copilot.infra.db.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])

_MAX_LOGIN_FAILURES = 5
_LOCKOUT_SECONDS = 15 * 60
_LOGIN_FAILURES: dict[str, tuple[int, datetime | None]] = {}


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105


def _login_key(request: Request, email: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{client_host}:{email.lower()}"


def _check_login_lock(key: str) -> None:
    failures, locked_until = _LOGIN_FAILURES.get(key, (0, None))
    if failures >= _MAX_LOGIN_FAILURES and locked_until is not None:
        if datetime.now(UTC) < locked_until:
            raise AuthenticationError("로그인 시도가 너무 많습니다. 잠시 후 다시 시도해주세요.")
        _LOGIN_FAILURES.pop(key, None)


def _record_login_failure(key: str) -> None:
    failures, _ = _LOGIN_FAILURES.get(key, (0, None))
    failures += 1
    locked_until = (
        datetime.now(UTC) + timedelta(seconds=_LOCKOUT_SECONDS)
        if failures >= _MAX_LOGIN_FAILURES
        else None
    )
    _LOGIN_FAILURES[key] = (failures, locked_until)


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    key = _login_key(request, body.email)
    _check_login_lock(key)

    credentials_valid = (
        user is not None and user.is_active and verify_password(body.password, user.hashed_password)
    )
    if not credentials_valid:
        _record_login_failure(key)
        raise AuthenticationError("이메일 또는 비밀번호가 올바르지 않습니다.")

    _LOGIN_FAILURES.pop(key, None)
    token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        client_company_id=user.client_company_id,
    )
    return TokenResponse(access_token=token)

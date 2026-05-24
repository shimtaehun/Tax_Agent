from fastapi import APIRouter, Depends
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.api.deps import get_db
from tax_copilot.auth.jwt import create_access_token
from tax_copilot.auth.password import verify_password
from tax_copilot.core.exceptions import AuthenticationError
from tax_copilot.infra.db.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    credentials_valid = (
        user is not None and user.is_active and verify_password(body.password, user.hashed_password)
    )
    if not credentials_valid:
        raise AuthenticationError("이메일 또는 비밀번호가 올바르지 않습니다.")

    token = create_access_token(
        user_id=user.id,
        tenant_id=user.tenant_id,
        role=user.role,
        client_company_id=user.client_company_id,
    )
    return TokenResponse(access_token=token)

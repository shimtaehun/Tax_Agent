from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from tax_copilot.core.config import settings
from tax_copilot.core.exceptions import AuthenticationError

_ALGORITHM = "HS256"
_ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 8  # 8시간


def create_access_token(
    user_id: int,
    tenant_id: int,
    role: str,
    client_company_id: int | None = None,
) -> str:
    expire = datetime.now(UTC) + timedelta(minutes=_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload: dict[str, object] = {
        "sub": str(user_id),
        "tenant_id": tenant_id,
        "role": role,
        "exp": expire,
    }
    if client_company_id is not None:
        payload["client_company_id"] = client_company_id
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)


_REQUIRED_CLAIMS = ("sub", "tenant_id", "role")


def decode_access_token(token: str) -> dict[str, object]:
    """Decode and validate a JWT. Raises AuthenticationError on failure."""
    try:
        payload: dict[str, object] = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
    except JWTError as exc:
        raise AuthenticationError("유효하지 않은 토큰입니다.") from exc

    missing = [c for c in _REQUIRED_CLAIMS if c not in payload]
    if missing:
        raise AuthenticationError(f"토큰에 필수 클레임이 없습니다: {missing}")
    return payload

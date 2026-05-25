import bcrypt

from tax_copilot.core.exceptions import ValidationError

_BCRYPT_MAX_BYTES = 72


def hash_password(plain: str) -> str:
    if len(plain.encode()) > _BCRYPT_MAX_BYTES:
        raise ValidationError("비밀번호는 72바이트를 초과할 수 없습니다.")
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    if len(plain.encode()) > _BCRYPT_MAX_BYTES:
        return False
    return bcrypt.checkpw(plain.encode(), hashed.encode())

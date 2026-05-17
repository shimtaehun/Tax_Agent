import pytest

from tax_copilot.core.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from tax_copilot.core.exceptions import ValidationError


def test_password_hash_and_verify() -> None:
    hashed = hash_password("secret123")
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)


def test_jwt_roundtrip() -> None:
    token = create_access_token(user_id=1, tenant_id=2, role="admin")
    payload = decode_access_token(token)
    assert payload["sub"] == "1"
    assert payload["tenant_id"] == 2
    assert payload["role"] == "admin"


def test_invalid_token_raises() -> None:
    with pytest.raises(ValidationError):
        decode_access_token("not.a.valid.token")

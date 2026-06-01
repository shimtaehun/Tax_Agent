"""auth/ 패키지 단위 테스트."""

import pytest

from tax_copilot.auth.jwt import create_access_token, decode_access_token
from tax_copilot.auth.password import hash_password, verify_password
from tax_copilot.auth.permissions import require_admin, require_staff_or_admin
from tax_copilot.core.exceptions import AuthenticationError, AuthorizationError


class TestPassword:
    def test_verify_correct_password(self) -> None:
        hashed = hash_password("correct")
        assert verify_password("correct", hashed) is True

    def test_reject_wrong_password(self) -> None:
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_hash_is_different_each_time(self) -> None:
        # bcrypt은 salt가 달라서 같은 비밀번호도 해시값이 다름
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2


class TestJWT:
    def test_round_trip(self) -> None:
        token = create_access_token(user_id=1, tenant_id=10, role="admin")
        payload = decode_access_token(token)
        assert payload["sub"] == "1"
        assert payload["tenant_id"] == 10
        assert payload["role"] == "admin"

    def test_invalid_token_raises(self) -> None:
        with pytest.raises(AuthenticationError):
            decode_access_token("not.a.valid.token")

    def test_tampered_token_raises(self) -> None:
        token = create_access_token(user_id=1, tenant_id=10, role="admin")
        tampered = token[:-5] + "XXXXX"
        with pytest.raises(AuthenticationError):
            decode_access_token(tampered)


class TestPermissions:
    def test_admin_passes_require_admin(self) -> None:
        require_admin("admin")  # 예외 없음

    def test_client_fails_require_admin(self) -> None:
        with pytest.raises(AuthorizationError):
            require_admin("client")

    def test_staff_passes_require_staff_or_admin(self) -> None:
        require_staff_or_admin("staff")  # 예외 없음

    def test_admin_passes_require_staff_or_admin(self) -> None:
        require_staff_or_admin("admin")  # 예외 없음

    def test_client_fails_require_staff_or_admin(self) -> None:
        with pytest.raises(AuthorizationError):
            require_staff_or_admin("client")


class TestLoginRateLimit:
    def test_locks_after_repeated_failures(self) -> None:
        from tax_copilot.api.v1.auth import (
            _LOGIN_FAILURES,
            _MAX_LOGIN_FAILURES,
            _check_login_lock,
            _record_login_failure,
        )

        key = "test:blocked@example.com"
        _LOGIN_FAILURES.pop(key, None)
        for _ in range(_MAX_LOGIN_FAILURES):
            _record_login_failure(key)

        with pytest.raises(AuthenticationError, match="로그인 시도가 너무 많습니다"):
            _check_login_lock(key)

        _LOGIN_FAILURES.pop(key, None)

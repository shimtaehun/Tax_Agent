from tax_copilot.core.exceptions import AuthorizationError
from tax_copilot.infra.db.models.user import ROLE_ADMIN, ROLE_STAFF


def require_admin(role: str) -> None:
    """Raise AuthorizationError unless the caller is an admin."""
    if role != ROLE_ADMIN:
        raise AuthorizationError("관리자 권한이 필요합니다.")


def require_staff_or_admin(role: str) -> None:
    """Raise AuthorizationError unless the caller is staff or admin."""
    if role not in (ROLE_STAFF, ROLE_ADMIN):
        raise AuthorizationError("직원 이상 권한이 필요합니다.")

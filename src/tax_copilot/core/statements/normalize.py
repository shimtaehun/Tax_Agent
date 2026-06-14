"""카드사 결제내역 원본 셀 값을 정규화하는 순수 헬퍼.

core/ 레이어이므로 외부 라이브러리 없음 (표준 라이브러리만 사용).
카드사마다 엑셀 셀 형식이 제각각이라 파서가 공통으로 쓰는 변환기를 모았다.
"""

from __future__ import annotations

import re
from datetime import date, time

# 금액 셀에서 숫자/부호 외 문자를 제거하기 위한 패턴 (콤마, '원', 공백 등)
_NON_AMOUNT = re.compile(r"[^0-9\-]")
_DIGITS_ONLY = re.compile(r"^\d{8}$")
# '2026년 06월 11일' / '2026년 6월 1일' 형식
_KOREAN_YMD = re.compile(r"(\d{4})\s*년\s*(\d{1,2})\s*월\s*(\d{1,2})\s*일")
# 'HH:MM' 또는 'HH:MM:SS'
_HHMMSS = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")


def parse_amount(value: object) -> int | None:
    """'1,234,000원' / '10000' / 50000 / '-30,000' → int. 변환 불가 시 None.

    카드 취소 건은 음수로 표기되기도 해서 부호('-')는 보존한다.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # bool은 int 하위형이므로 명시적으로 배제
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if not isinstance(value, str):
        return None
    cleaned = _NON_AMOUNT.sub("", value).strip()
    if cleaned in ("", "-"):
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def parse_statement_date(value: object) -> date | None:
    """'2026-05-10' / '2026.05.10' / '2026/05/10' / '20260510' → date.

    파싱 불가 시 None (행 단위 부분 실패를 허용하기 위함).
    """
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    korean = _KOREAN_YMD.search(text)
    if korean:
        try:
            return date(int(korean[1]), int(korean[2]), int(korean[3]))
        except ValueError:
            return None
    if _DIGITS_ONLY.match(text):
        try:
            return date(int(text[0:4]), int(text[4:6]), int(text[6:8]))
        except ValueError:
            return None
    normalized = text.replace(".", "-").replace("/", "-")
    try:
        return date.fromisoformat(normalized)
    except ValueError:
        return None


def parse_statement_time(value: object) -> time | None:
    """'11:57' / '00:22' / '09:05:30' → time. 파싱 불가 시 None."""
    if value is None:
        return None
    if isinstance(value, time):
        return value
    if not isinstance(value, str):
        return None
    match = _HHMMSS.match(value.strip())
    if not match:
        return None
    hour, minute, second = int(match[1]), int(match[2]), int(match[3] or 0)
    try:
        return time(hour, minute, second)
    except ValueError:
        return None

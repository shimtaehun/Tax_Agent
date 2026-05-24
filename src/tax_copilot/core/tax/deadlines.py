"""세금 신고 기한 계산 순수 함수.

한국 세법 기준:
- 부가세 1기 예정: 4월 25일
- 부가세 1기 확정: 7월 25일
- 부가세 2기 예정: 10월 25일
- 부가세 2기 확정: 다음 해 1월 25일
- 종합소득세: 5월 31일
- 법인세: 3월 31일 (12월 결산 법인 기준)
"""

from datetime import date
from typing import Any

_DEADLINES: list[tuple[str, int, int, int, str]] = [
    # (tax_type, month, day, year_offset, description)
    ("법인세", 3, 31, 0, "법인세 확정신고 (12월 결산)"),
    ("VAT_1기_예정", 4, 25, 0, "부가세 1기 예정신고 (1~3월분)"),
    ("종합소득세", 5, 31, 0, "종합소득세 확정신고"),
    ("VAT_1기_확정", 7, 25, 0, "부가세 1기 확정신고 (1~6월분)"),
    ("VAT_2기_예정", 10, 25, 0, "부가세 2기 예정신고 (7~9월분)"),
    ("VAT_2기_확정", 1, 25, 1, "부가세 2기 확정신고 (7~12월분)"),  # year+1
]


def generate_annual_deadlines(fiscal_year: int) -> list[dict[str, Any]]:
    """주어진 회계연도의 세금 신고 기한 목록을 반환한다.

    Args:
        fiscal_year: 회계연도 (예: 2026)

    Returns:
        tax_type, due_date, fiscal_year, description 키를 갖는 dict 목록.
    """
    deadlines = []
    for tax_type, month, day, year_offset, description in _DEADLINES:
        due_date = date(fiscal_year + year_offset, month, day)
        deadlines.append(
            {
                "tax_type": tax_type,
                "due_date": due_date,
                "fiscal_year": fiscal_year,
                "description": description,
            }
        )
    return deadlines

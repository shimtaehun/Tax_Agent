"""통장 거래내역 CSV 범용 파서.

은행마다 엑셀/CSV 양식이 다르므로, 한국 은행 거래내역에서 흔한 한글 헤더명을
유연하게 매핑해 정규화한다. core/ 레이어이므로 표준 라이브러리 + pydantic만 사용.
"""

from __future__ import annotations

import csv
import io
from datetime import date

from pydantic import BaseModel

# 컬럼 의미 → 가능한 헤더명 후보 (소문자/공백제거 비교)
_HEADER_ALIASES: dict[str, list[str]] = {
    "transaction_date": ["거래일자", "거래일시", "거래일", "일자", "날짜", "거래날짜"],
    "description": ["적요", "내용", "거래내용", "메모", "기재내용"],
    "counterparty": ["거래처", "의뢰인", "수취인", "보내는분", "받는분", "의뢰인/수취인", "상대방"],
    "withdrawal_krw": ["출금", "출금액", "출금금액", "지급", "지급액", "차변"],
    "deposit_krw": ["입금", "입금액", "입금금액", "예입", "예입액", "대변"],
    "balance_krw": ["잔액", "거래후잔액", "거래후 잔액", "남은잔액"],
}


class BankRow(BaseModel):
    transaction_date: date | None = None
    description: str | None = None
    counterparty: str | None = None
    deposit_krw: int = 0
    withdrawal_krw: int = 0
    balance_krw: int | None = None


def _norm(s: str) -> str:
    return s.replace(" ", "").replace("﻿", "").strip().lower()


def _build_header_map(headers: list[str]) -> dict[str, int]:
    """정규화 헤더명을 컬럼 인덱스로 매핑한다."""
    norm_headers = [_norm(h) for h in headers]
    mapping: dict[str, int] = {}
    for field, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            target = _norm(alias)
            if target in norm_headers:
                mapping[field] = norm_headers.index(target)
                break
    return mapping


def _parse_amount(value: str | None) -> int:
    if not value:
        return 0
    cleaned = value.replace(",", "").replace("원", "").replace("₩", "").strip()
    if not cleaned or cleaned == "-":
        return 0
    try:
        return abs(int(float(cleaned)))
    except ValueError:
        return 0


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    raw = value.strip()[:10].replace(".", "-").replace("/", "-").rstrip("-")
    parts = raw.split("-")
    if len(parts) >= 3:
        try:
            return date(int(parts[0]), int(parts[1]), int(parts[2]))
        except ValueError:
            return None
    # YYYYMMDD
    digits = value.strip()[:8]
    if digits.isdigit() and len(digits) == 8:
        try:
            return date(int(digits[:4]), int(digits[4:6]), int(digits[6:8]))
        except ValueError:
            return None
    return None


def parse_bank_csv(text: str) -> list[BankRow]:
    """범용 통장 CSV 텍스트를 BankRow 목록으로 정규화한다.

    필수 인식 컬럼: 거래일자, 출금/입금 중 하나 이상. 헤더를 못 찾으면 빈 목록.
    """
    text = text.lstrip("﻿")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return []

    header_map = _build_header_map(rows[0])
    if "transaction_date" not in header_map:
        return []

    def cell(row: list[str], field: str) -> str | None:
        idx = header_map.get(field)
        if idx is None or idx >= len(row):
            return None
        return row[idx]

    result: list[BankRow] = []
    for row in rows[1:]:
        if not any(c.strip() for c in row):
            continue
        deposit = _parse_amount(cell(row, "deposit_krw"))
        withdrawal = _parse_amount(cell(row, "withdrawal_krw"))
        if deposit == 0 and withdrawal == 0:
            continue
        result.append(
            BankRow(
                transaction_date=_parse_date(cell(row, "transaction_date")),
                description=(cell(row, "description") or None),
                counterparty=(cell(row, "counterparty") or None),
                deposit_krw=deposit,
                withdrawal_krw=withdrawal,
                balance_krw=(_parse_amount(cell(row, "balance_krw")) or None),
            )
        )
    return result

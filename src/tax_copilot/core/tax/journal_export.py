"""분개 전표 → 회계프로그램 import용 표준 양식 변환.

더존 Smart-A / 세무사랑 등 대부분의 회계프로그램은 '일반전표 엑셀(CSV) 가져오기'를
지원하며, 공통 컬럼(일자·구분·계정과목·차변금액·대변금액·거래처·적요)을 사용한다.
여기서는 특정 벤더에 종속되지 않는 범용 표준 분개 CSV를 만든다. core/ 레이어라
표준 라이브러리(csv, io)만 사용한다.
"""

from __future__ import annotations

import csv
import io
from typing import Any

from tax_copilot.core.tax.journal import JournalEntry

# 범용 일반전표 컬럼 (한글 헤더 — 회계프로그램 매핑 시 직관적)
COLUMNS = ["일자", "거래처", "구분", "계정과목", "차변금액", "대변금액", "적요"]


def journal_entries_to_rows(entries: list[JournalEntry]) -> list[dict[str, Any]]:
    """전표 목록을 한 줄=한 분개라인 형태의 행 dict 목록으로 펼친다."""
    rows: list[dict[str, Any]] = []
    for entry in entries:
        for line in entry.lines:
            is_debit = line.side == "차변"
            rows.append(
                {
                    "일자": entry.entry_date.isoformat(),
                    "거래처": entry.counterparty or "",
                    "구분": line.side,
                    "계정과목": line.account_title,
                    "차변금액": line.amount_krw if is_debit else 0,
                    "대변금액": 0 if is_debit else line.amount_krw,
                    "적요": line.description or entry.summary,
                }
            )
    return rows


def rows_to_csv(rows: list[dict[str, Any]]) -> str:
    """행 목록을 CSV 문자열로 직렬화한다 (헤더 포함)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow({col: row.get(col, "") for col in COLUMNS})
    return buffer.getvalue()


def journal_entries_to_csv(entries: list[JournalEntry]) -> str:
    """전표 목록을 회계프로그램 import용 CSV 문자열로 변환한다."""
    return rows_to_csv(journal_entries_to_rows(entries))

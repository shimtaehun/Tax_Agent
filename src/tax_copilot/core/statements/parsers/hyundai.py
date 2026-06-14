"""현대카드 '실시간 이용내역' export 파서.

현대카드 웹 다운로드는 확장자가 .xls지만 실제로는 HTML 표다. 외부 의존성 없이
표준 라이브러리 html.parser로 표를 추출한다.

표 컬럼(11개): 승인일 · 승인시각 · 카드구분 · 카드종류(카드번호) · 가맹점명 ·
승인금액 · 이용구분 · 할부개월 · 승인번호 · 취소일 · 승인구분
"""

from __future__ import annotations

from html.parser import HTMLParser

from tax_copilot.core.statements.normalize import (
    parse_amount,
    parse_statement_date,
    parse_statement_time,
)
from tax_copilot.core.statements.registry import register_parser
from tax_copilot.core.statements.schemas import StatementRow

# 데이터 행을 식별하는 헤더 셀 텍스트와 컬럼 수
_HEADER_MARKER = "승인번호"
_COLUMN_COUNT = 11
_COLUMNS = (
    "승인일",
    "승인시각",
    "카드구분",
    "카드종류",
    "가맹점명",
    "승인금액",
    "이용구분",
    "할부개월",
    "승인번호",
    "취소일",
    "승인구분",
)


class _TableExtractor(HTMLParser):
    """모든 <tr>의 셀(td/th) 텍스트를 list[list[str]]로 수집한다."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._current: list[str] | None = None
        self._in_cell = False
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag == "tr":
            self._current = []
        elif tag in ("td", "th") and self._current is not None:
            self._in_cell = True
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag in ("td", "th") and self._in_cell:
            # 셀 안 줄바꿈/들여쓰기 공백을 단일 공백으로 축약 후 trim.
            text = " ".join("".join(self._parts).split())
            if self._current is not None:
                self._current.append(text)
            self._in_cell = False
        elif tag == "tr" and self._current is not None:
            self.rows.append(self._current)
            self._current = None

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._parts.append(data)


class HyundaiCardParser:
    """현대카드 이용내역 HTML(.xls)을 StatementRow 리스트로 변환한다."""

    card_company = "hyundai"

    def matches(self, filename: str, header: list[str]) -> bool:
        name = filename.lower()
        return "hyundai" in name or "현대" in filename

    def parse(self, filename: str, content: bytes) -> list[StatementRow]:
        extractor = _TableExtractor()
        extractor.feed(content.decode("utf-8", errors="replace"))

        rows: list[StatementRow] = []
        header_seen = False
        for cells in extractor.rows:
            if len(cells) != _COLUMN_COUNT:
                continue
            if not header_seen:
                if _HEADER_MARKER in cells:
                    header_seen = True
                continue
            row = self._to_row(cells)
            # 소계/합계 행은 승인일이 '-'이고 승인번호가 비어 거래로 볼 수 없다.
            if row.transaction_date is None and not row.approval_no:
                continue
            rows.append(row)
        return rows

    @staticmethod
    def _to_row(cells: list[str]) -> StatementRow:
        cancel_date = cells[9].strip()
        cancelled = cells[10] == "취소" or cancel_date not in ("", "-")
        return StatementRow(
            transaction_date=parse_statement_date(cells[0]),
            transaction_time=parse_statement_time(cells[1]),
            card_no_masked=cells[3] or None,
            merchant_name=cells[4] or None,
            total_amount_krw=parse_amount(cells[5]),
            installment_months=parse_amount(cells[7]),
            approval_no=cells[8] or None,
            cancelled=cancelled,
            raw=dict(zip(_COLUMNS, cells, strict=True)),
        )


register_parser(HyundaiCardParser())

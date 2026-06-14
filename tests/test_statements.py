"""카드사 결제내역(엑셀) 파싱·적재 테스트."""

from dataclasses import FrozenInstanceError
from datetime import date, time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from tax_copilot.core.exceptions import ValidationError
from tax_copilot.core.statements.ingest import ingest_statement_rows
from tax_copilot.core.statements.normalize import (
    parse_amount,
    parse_statement_date,
    parse_statement_time,
)
from tax_copilot.core.statements.registry import (
    StatementParserRegistry,
    get_parser,
    register_parser,
)
from tax_copilot.core.statements.schemas import StatementRow
from tax_copilot.infra.db.models.card_transaction import CardTransaction

# --- 정규화 헬퍼 -----------------------------------------------------------


def test_parse_amount_strips_separators_and_won() -> None:
    assert parse_amount("1,234,000원") == 1_234_000
    assert parse_amount("10000") == 10_000
    assert parse_amount(50_000) == 50_000


def test_parse_amount_handles_blank_and_invalid() -> None:
    assert parse_amount("") is None
    assert parse_amount(None) is None
    assert parse_amount("-") is None


def test_parse_amount_handles_negative_cancellation() -> None:
    # 카드 취소 건은 음수 금액으로 표기되기도 한다.
    assert parse_amount("-30,000") == -30_000


def test_parse_statement_date_accepts_common_korean_formats() -> None:
    assert parse_statement_date("2026-05-10") == date(2026, 5, 10)
    assert parse_statement_date("2026.05.10") == date(2026, 5, 10)
    assert parse_statement_date("2026/05/10") == date(2026, 5, 10)
    assert parse_statement_date("20260510") == date(2026, 5, 10)


def test_parse_statement_date_accepts_korean_yymmdd_words() -> None:
    # 현대카드 웹 export는 '2026년 06월 11일' 형식을 쓴다.
    assert parse_statement_date("2026년 06월 11일") == date(2026, 6, 11)
    assert parse_statement_date("  2026년 6월 1일  ") == date(2026, 6, 1)


def test_parse_statement_date_returns_none_for_unparseable() -> None:
    assert parse_statement_date("") is None
    assert parse_statement_date(None) is None
    assert parse_statement_date("not-a-date") is None
    assert parse_statement_date("-") is None


def test_parse_statement_time_accepts_hhmm() -> None:
    from datetime import time

    assert parse_statement_time("11:57") == time(11, 57)
    assert parse_statement_time("00:22") == time(0, 22)
    assert parse_statement_time("09:05:30") == time(9, 5, 30)


def test_parse_statement_time_returns_none_for_blank() -> None:
    assert parse_statement_time("") is None
    assert parse_statement_time(None) is None
    assert parse_statement_time("-") is None


# --- 도메인 모델 -----------------------------------------------------------


def test_statement_row_is_immutable() -> None:
    row = StatementRow(
        transaction_date=date(2026, 5, 10),
        merchant_name="스타벅스 강남점",
        approval_no="12345678",
        total_amount_krw=4_500,
    )
    assert row.transaction_date == date(2026, 5, 10)
    assert row.currency == "KRW"
    assert row.cancelled is False
    with pytest.raises(FrozenInstanceError):
        row.total_amount_krw = 0  # type: ignore[misc]


# --- 파서 레지스트리 -------------------------------------------------------


def _fake_parser(card_company: str):
    class _Parser:
        def __init__(self) -> None:
            self.card_company = card_company

        def matches(self, filename: str, header: list[str]) -> bool:
            # 전역 레지스트리 자동 판별(detect_parser)을 오염시키지 않도록 False.
            return False

        def parse(self, filename: str, content: bytes) -> list[StatementRow]:
            return []

    return _Parser()


def test_register_and_get_parser_by_card_company() -> None:
    registry = StatementParserRegistry()
    parser = _fake_parser("shinhan")
    registry.register(parser)
    assert registry.get("shinhan") is parser


def test_get_unknown_parser_raises() -> None:
    registry = StatementParserRegistry()
    with pytest.raises(ValidationError):
        registry.get("nonexistent_card")


def test_module_level_registry_roundtrip() -> None:
    parser = _fake_parser("kb_test_only")
    register_parser(parser)
    assert get_parser("kb_test_only") is parser


# --- 현대카드 파서 (실제 export 구조 골든 테스트) ---------------------------

_FIXTURE = Path(__file__).parent / "fixtures" / "statements" / "hyundai_sample.xls"


def test_hyundai_parser_is_registered() -> None:
    parser = get_parser("hyundai")
    assert parser.card_company == "hyundai"


def test_hyundai_parser_matches_by_filename() -> None:
    parser = get_parser("hyundai")
    assert parser.matches("hyundaicard_20260611.xls", []) is True
    assert parser.matches("shinhan_2026.xlsx", []) is False


def test_hyundai_parser_parses_normal_row() -> None:
    parser = get_parser("hyundai")
    rows = parser.parse("hyundaicard_20260611.xls", _FIXTURE.read_bytes())

    assert len(rows) == 2
    first = rows[0]
    assert first.transaction_date == date(2026, 6, 11)
    assert first.transaction_time == time(11, 57)
    assert first.card_no_masked == "4***-****-****-130*"
    assert first.merchant_name == "공간의미"
    assert first.total_amount_krw == 7_500
    assert first.installment_months == 0
    assert first.approval_no == "00688404"
    assert first.cancelled is False
    assert first.currency == "KRW"


def test_hyundai_parser_flags_cancelled_row() -> None:
    parser = get_parser("hyundai")
    rows = parser.parse("hyundaicard_20260611.xls", _FIXTURE.read_bytes())

    second = rows[1]
    assert second.merchant_name == "뉴모닝마트"
    assert second.total_amount_krw == 2_650
    assert second.installment_months == 3
    assert second.approval_no == "00111222"
    assert second.cancelled is True


# --- ingest (DB 적재) ------------------------------------------------------


def _mock_db(existing: list[object]) -> MagicMock:
    """중복 조회마다 scalar_one_or_none이 existing 값을 순서대로 돌려주는 목 세션."""
    results = []
    for value in existing:
        result = MagicMock()
        result.scalar_one_or_none.return_value = value
        results.append(result)
    db = MagicMock()
    db.execute = AsyncMock(side_effect=results)
    db.add = MagicMock()
    db.commit = AsyncMock()
    return db


def _row(approval_no: str | None, amount: int = 4_500) -> StatementRow:
    return StatementRow(
        transaction_date=date(2026, 5, 10),
        merchant_name="스타벅스 강남점",
        approval_no=approval_no,
        total_amount_krw=amount,
    )


@pytest.mark.anyio
async def test_ingest_imports_new_rows() -> None:
    db = _mock_db(existing=[None, None])

    result = await ingest_statement_rows(
        db,
        [_row("A1"), _row("A2")],
        tenant_id=1,
        client_company_id=1,
        uploaded_by=1,
        source_filename="shinhan_2026_05.xlsx",
        card_company="shinhan",
    )

    assert result.imported == 2
    assert result.skipped == 0
    assert db.add.call_count == 2
    db.commit.assert_awaited_once()
    added = db.add.call_args_list[0].args[0]
    assert isinstance(added, CardTransaction)
    assert added.card_company == "shinhan"
    assert added.tenant_id == 1
    assert added.approval_no == "A1"
    assert added.source_filename == "shinhan_2026_05.xlsx"
    # 적재 시점에 가맹점명 기반 계정과목이 분류된다 (스타벅스 → 복리후생비).
    assert added.account_code == "복리후생비"


@pytest.mark.anyio
async def test_ingest_skips_duplicate_approval_no() -> None:
    # 첫 행은 이미 존재(중복), 두 번째는 신규.
    db = _mock_db(existing=[CardTransaction(), None])

    result = await ingest_statement_rows(
        db,
        [_row("A1"), _row("A2")],
        tenant_id=1,
        client_company_id=1,
        uploaded_by=1,
        source_filename="s.xlsx",
        card_company="shinhan",
    )

    assert result.imported == 1
    assert result.skipped == 1
    assert db.add.call_count == 1


@pytest.mark.anyio
async def test_ingest_imports_rows_without_approval_no_without_dedup() -> None:
    # 승인번호 없는 행은 중복 조회 없이 그대로 적재한다.
    db = _mock_db(existing=[])

    result = await ingest_statement_rows(
        db,
        [_row(None)],
        tenant_id=1,
        client_company_id=1,
        uploaded_by=1,
        source_filename="s.xlsx",
        card_company="shinhan",
    )

    assert result.imported == 1
    assert result.skipped == 0
    db.execute.assert_not_awaited()
    db.add.assert_called_once()

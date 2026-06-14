"""삼중 대사 매칭 엔진 + 통장 CSV 파서 테스트."""

from datetime import date

from tax_copilot.core.bank import parse_bank_csv
from tax_copilot.core.tax.reconciliation import (
    BankItem,
    ReconCandidate,
    reconcile,
)


def test_exact_amount_and_date_matches() -> None:
    bank = [BankItem(id=1, transaction_date=date(2026, 3, 10), withdrawal_krw=11_000)]
    cands = [
        ReconCandidate(
            source_type="card",
            source_id=100,
            amount_krw=11_000,
            transaction_date=date(2026, 3, 10),
            direction="out",
        )
    ]
    result = reconcile(bank, cands)
    assert result.matched_count == 1
    assert result.matches[0].source_id == 100
    assert result.unmatched_bank_ids == []
    assert result.unmatched_candidates == []


def test_deposit_matches_sale_invoice() -> None:
    bank = [BankItem(id=1, transaction_date=date(2026, 3, 31), deposit_krw=1_100_000)]
    cands = [
        ReconCandidate(
            source_type="tax_invoice_sale",
            source_id=5,
            amount_krw=1_100_000,
            transaction_date=date(2026, 3, 30),
            direction="in",
        )
    ]
    result = reconcile(bank, cands)
    assert result.matched_count == 1


def test_direction_mismatch_does_not_match() -> None:
    bank = [BankItem(id=1, transaction_date=date(2026, 3, 10), deposit_krw=11_000)]
    cands = [
        ReconCandidate(
            source_type="card",
            source_id=100,
            amount_krw=11_000,
            transaction_date=date(2026, 3, 10),
            direction="out",
        )
    ]
    result = reconcile(bank, cands)
    assert result.matched_count == 0
    assert result.unmatched_bank_ids == [1]


def test_date_outside_tolerance_does_not_match() -> None:
    bank = [BankItem(id=1, transaction_date=date(2026, 3, 1), withdrawal_krw=5_000)]
    cands = [
        ReconCandidate(
            source_type="card",
            source_id=1,
            amount_krw=5_000,
            transaction_date=date(2026, 3, 20),
            direction="out",
        )
    ]
    result = reconcile(bank, cands, date_tolerance_days=3)
    assert result.matched_count == 0
    assert result.unmatched_bank_ids == [1]
    assert len(result.unmatched_candidates) == 1


def test_unmatched_bank_is_evidence_gap() -> None:
    bank = [BankItem(id=7, transaction_date=date(2026, 3, 10), withdrawal_krw=999_999)]
    result = reconcile(bank, [])
    assert result.unmatched_bank_ids == [7]


def test_candidate_consumed_only_once() -> None:
    bank = [
        BankItem(id=1, transaction_date=date(2026, 3, 10), withdrawal_krw=5_000),
        BankItem(id=2, transaction_date=date(2026, 3, 10), withdrawal_krw=5_000),
    ]
    cands = [
        ReconCandidate(
            source_type="card",
            source_id=1,
            amount_krw=5_000,
            transaction_date=date(2026, 3, 10),
            direction="out",
        )
    ]
    result = reconcile(bank, cands)
    assert result.matched_count == 1
    assert len(result.unmatched_bank_ids) == 1


def test_picks_nearest_date_candidate() -> None:
    bank = [BankItem(id=1, transaction_date=date(2026, 3, 10), withdrawal_krw=5_000)]
    cands = [
        ReconCandidate(
            source_type="card",
            source_id=10,
            amount_krw=5_000,
            transaction_date=date(2026, 3, 12),
            direction="out",
        ),
        ReconCandidate(
            source_type="card",
            source_id=11,
            amount_krw=5_000,
            transaction_date=date(2026, 3, 10),
            direction="out",
        ),
    ]
    result = reconcile(bank, cands)
    assert result.matches[0].source_id == 11


def test_parse_bank_csv_standard_headers() -> None:
    csv_text = (
        "거래일자,적요,거래처,출금,입금,잔액\n"
        '2026-03-10,카드대금,현대카드,"1,100,000",,"5,000,000"\n'
        '2026-03-15,급여이체,,,"2,000,000","7,000,000"\n'
    )
    rows = parse_bank_csv(csv_text)
    assert len(rows) == 2
    assert rows[0].transaction_date == date(2026, 3, 10)
    assert rows[0].withdrawal_krw == 1_100_000
    assert rows[0].deposit_krw == 0
    assert rows[1].deposit_krw == 2_000_000


def test_parse_bank_csv_alternative_headers_and_dotted_date() -> None:
    csv_text = "거래일시,내용,출금액,입금액\n2026.02.01,임차료,500000,0\n"
    rows = parse_bank_csv(csv_text)
    assert len(rows) == 1
    assert rows[0].transaction_date == date(2026, 2, 1)
    assert rows[0].withdrawal_krw == 500_000


def test_parse_bank_csv_no_recognizable_header_returns_empty() -> None:
    assert parse_bank_csv("foo,bar,baz\n1,2,3\n") == []

"""누락 증빙 감지 테스트."""

from datetime import date

from tax_copilot.core.tax.missing_evidence import (
    CardCharge,
    ReceiptRef,
    find_cards_missing_receipts,
)


def test_card_with_matching_receipt_is_not_missing() -> None:
    cards = [CardCharge(id=1, amount_krw=11_000, transaction_date=date(2026, 3, 10))]
    receipts = [ReceiptRef(id=9, amount_krw=11_000, transaction_date=date(2026, 3, 10))]
    assert find_cards_missing_receipts(cards, receipts) == []


def test_card_without_receipt_is_missing() -> None:
    cards = [
        CardCharge(id=1, amount_krw=11_000, transaction_date=date(2026, 3, 10), merchant_name="A")
    ]
    missing = find_cards_missing_receipts(cards, [])
    assert len(missing) == 1
    assert missing[0].id == 1


def test_amount_mismatch_is_missing() -> None:
    cards = [CardCharge(id=1, amount_krw=11_000, transaction_date=date(2026, 3, 10))]
    receipts = [ReceiptRef(id=9, amount_krw=10_000, transaction_date=date(2026, 3, 10))]
    assert len(find_cards_missing_receipts(cards, receipts)) == 1


def test_date_outside_tolerance_is_missing() -> None:
    cards = [CardCharge(id=1, amount_krw=11_000, transaction_date=date(2026, 3, 1))]
    receipts = [ReceiptRef(id=9, amount_krw=11_000, transaction_date=date(2026, 3, 20))]
    assert len(find_cards_missing_receipts(cards, receipts, date_tolerance_days=3)) == 1


def test_receipt_consumed_only_once() -> None:
    cards = [
        CardCharge(id=1, amount_krw=5_000, transaction_date=date(2026, 3, 10)),
        CardCharge(id=2, amount_krw=5_000, transaction_date=date(2026, 3, 10)),
    ]
    receipts = [ReceiptRef(id=9, amount_krw=5_000, transaction_date=date(2026, 3, 10))]
    missing = find_cards_missing_receipts(cards, receipts)
    assert len(missing) == 1

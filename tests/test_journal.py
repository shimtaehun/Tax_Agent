"""분개(전표) 자동 생성 및 CSV export 테스트."""

from datetime import date

from tax_copilot.core.tax.journal import (
    VAT_INPUT_ACCOUNT,
    VAT_OUTPUT_ACCOUNT,
    build_entry_from_receipt,
    build_entry_from_tax_invoice,
    build_purchase_entry,
    build_sale_entry,
    counter_account_for,
)
from tax_copilot.core.tax.journal_export import (
    COLUMNS,
    journal_entries_to_csv,
    journal_entries_to_rows,
)


def test_purchase_creditable_splits_vat_input() -> None:
    entry = build_purchase_entry(
        entry_date=date(2026, 3, 10),
        account_title="복리후생비",
        supply_value_krw=10_000,
        vat_krw=1_000,
        vat_creditable=True,
        counter_account="미지급금",
        summary="스타벅스",
        source_type="card",
    )
    titles = {line.account_title: line.amount_krw for line in entry.lines}
    assert titles["복리후생비"] == 10_000
    assert titles[VAT_INPUT_ACCOUNT] == 1_000
    assert titles["미지급금"] == 11_000
    assert entry.is_balanced


def test_purchase_non_creditable_folds_vat_into_expense() -> None:
    entry = build_purchase_entry(
        entry_date=date(2026, 3, 10),
        account_title="접대비",
        supply_value_krw=10_000,
        vat_krw=1_000,
        vat_creditable=False,
        counter_account="현금",
        summary="식당",
        source_type="receipt",
    )
    debit = [line for line in entry.lines if line.side == "차변"]
    assert len(debit) == 1
    assert debit[0].account_title == "접대비"
    assert debit[0].amount_krw == 11_000  # 부가세가 비용에 산입됨
    assert all(line.account_title != VAT_INPUT_ACCOUNT for line in entry.lines)
    assert entry.is_balanced


def test_sale_entry_splits_vat_output() -> None:
    entry = build_sale_entry(
        entry_date=date(2026, 3, 31),
        supply_value_krw=1_000_000,
        vat_krw=100_000,
        counter_account="외상매출금",
        summary="(주)거래처",
    )
    titles = {line.account_title: line.amount_krw for line in entry.lines}
    assert titles["외상매출금"] == 1_100_000
    assert titles["매출"] == 1_000_000
    assert titles[VAT_OUTPUT_ACCOUNT] == 100_000
    assert entry.is_balanced


def test_counter_account_mapping() -> None:
    assert counter_account_for("credit_card_slip") == "미지급금"
    assert counter_account_for("cash_receipt") == "현금"
    assert counter_account_for(None) == "미지급금"


def test_build_entry_from_receipt() -> None:
    receipt = {
        "id": 7,
        "transaction_date": date(2026, 2, 1),
        "account_code": "여비교통비",
        "parsed_data": {
            "evidence_type": "credit_card_slip",
            "vat_creditable": True,
            "merchant_name": "카카오택시",
            "calculation_result": {"supply_value_krw": 9_091, "vat_krw": 909},
        },
    }
    entry = build_entry_from_receipt(receipt)
    assert entry is not None
    assert entry.source_id == 7
    assert entry.counterparty == "카카오택시"
    assert entry.is_balanced
    assert entry.debit_total == 10_000


def test_build_entry_from_receipt_returns_none_without_amount() -> None:
    receipt = {"id": 1, "transaction_date": date(2026, 2, 1), "parsed_data": {}}
    assert build_entry_from_receipt(receipt) is None


def test_build_entry_from_receipt_returns_none_without_date() -> None:
    receipt = {
        "id": 1,
        "transaction_date": None,
        "parsed_data": {"calculation_result": {"supply_value_krw": 100, "vat_krw": 10}},
    }
    assert build_entry_from_receipt(receipt) is None


def test_build_entry_from_purchase_invoice() -> None:
    invoice = {
        "id": 3,
        "direction": "purchase",
        "issue_date": date(2026, 1, 15),
        "supplier_name": "(주)공급처",
        "supply_value_krw": 500_000,
        "vat_krw": 50_000,
    }
    entry = build_entry_from_tax_invoice(invoice)
    assert entry is not None
    assert entry.source_type == "tax_invoice_purchase"
    assert entry.is_balanced
    titles = {line.account_title for line in entry.lines}
    assert "외상매입금" in titles
    assert VAT_INPUT_ACCOUNT in titles


def test_build_entry_from_sale_invoice() -> None:
    invoice = {
        "id": 4,
        "direction": "sale",
        "issue_date": date(2026, 1, 20),
        "recipient_name": "(주)매출처",
        "supply_value_krw": 200_000,
        "vat_krw": 20_000,
    }
    entry = build_entry_from_tax_invoice(invoice)
    assert entry is not None
    assert entry.source_type == "tax_invoice_sale"
    assert entry.is_balanced


def test_iso_string_date_is_coerced() -> None:
    receipt = {
        "id": 9,
        "transaction_date": "2026-02-01T00:00:00",
        "account_code": "소모품비",
        "parsed_data": {
            "evidence_type": "cash_receipt",
            "calculation_result": {"supply_value_krw": 1_000, "vat_krw": 100},
        },
    }
    entry = build_entry_from_receipt(receipt)
    assert entry is not None
    assert entry.entry_date == date(2026, 2, 1)


def test_export_rows_have_debit_credit_columns() -> None:
    entry = build_purchase_entry(
        entry_date=date(2026, 3, 10),
        account_title="복리후생비",
        supply_value_krw=10_000,
        vat_krw=1_000,
        vat_creditable=True,
        counter_account="미지급금",
        summary="스타벅스",
        source_type="card",
    )
    rows = journal_entries_to_rows([entry])
    assert len(rows) == 3
    debit_sum = sum(r["차변금액"] for r in rows)
    credit_sum = sum(r["대변금액"] for r in rows)
    assert debit_sum == credit_sum == 11_000


def test_export_csv_has_header_and_lines() -> None:
    entry = build_sale_entry(
        entry_date=date(2026, 3, 31),
        supply_value_krw=1_000_000,
        vat_krw=100_000,
        counter_account="외상매출금",
        summary="(주)거래처",
    )
    csv_text = journal_entries_to_csv([entry])
    lines = csv_text.strip().splitlines()
    assert lines[0] == ",".join(COLUMNS)
    assert len(lines) == 4  # 헤더 + 차변1 + 대변2

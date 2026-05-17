from datetime import date
from typing import Protocol

from tax_copilot.core.schemas import ParsedReceipt


class ReceiptExtractor(Protocol):
    def extract(self, *, file_path: str, mime_type: str) -> ParsedReceipt:
        """Extract a structured receipt from an already quality-checked file."""


class StaticReceiptExtractor:
    def __init__(self, parsed_receipt: ParsedReceipt | None = None) -> None:
        self._parsed_receipt = parsed_receipt or ParsedReceipt(
            merchant_name="Mock Merchant",
            transaction_date=date(2026, 1, 15),
            total_amount_krw=11000,
            evidence_type="credit_card_slip",
            payment_method="card",
        )

    def extract(self, *, file_path: str, mime_type: str) -> ParsedReceipt:
        return self._parsed_receipt

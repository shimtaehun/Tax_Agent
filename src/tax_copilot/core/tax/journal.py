"""분개(전표) 자동 생성 순수 함수.

파싱·분류가 끝난 영수증/세금계산서/카드내역을 복식부기 차변·대변
전표(JournalEntry)로 변환한다. core/ 레이어이므로 외부 라이브러리 없이
표준 라이브러리 + pydantic만 사용한다.

핵심 분개 규칙(한국 일반 세무 기장 기준):
- 매입 비용(공제): 차) 비용계정 공급가액 + 부가세대급금 매입세액 / 대) 결제계정 합계
- 매입 비용(불공제): 차) 비용계정 (공급가액+부가세) / 대) 결제계정 합계
  (불공제 매입세액은 비용 원가에 산입한다)
- 매출 세금계산서: 차) 외상매출금 합계 / 대) 매출 공급가액 + 부가세예수금
- 매입 세금계산서: 차) 매입계정 공급가액 + 부가세대급금 / 대) 외상매입금 합계

불변식: 한 전표의 차변 합계 == 대변 합계.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field

# 부가세 관련 계정과목 (고정)
VAT_INPUT_ACCOUNT = "부가세대급금"  # 매입세액 (자산)
VAT_OUTPUT_ACCOUNT = "부가세예수금"  # 매출세액 (부채)
SALES_ACCOUNT = "매출"

# 증빙·결제 종류 → 대변(상대) 계정 기본값
_COUNTER_ACCOUNT_BY_EVIDENCE: dict[str, str] = {
    "credit_card_slip": "미지급금",
    "card": "미지급금",
    "cash_receipt": "현금",
    "cash": "현금",
    "tax_invoice": "외상매입금",
    "invoice": "외상매입금",
    "simplified_receipt": "현금",
    "simple_receipt": "현금",
    "receipt": "현금",
}
_DEFAULT_COUNTER_ACCOUNT = "미지급금"

SourceType = Literal["receipt", "card", "tax_invoice_purchase", "tax_invoice_sale"]
LineSide = Literal["차변", "대변"]


class JournalLine(BaseModel):
    """전표 한 줄 (계정별 차변 또는 대변 금액)."""

    side: LineSide
    account_title: str
    amount_krw: int = Field(ge=0)
    description: str | None = None


class JournalEntry(BaseModel):
    """하나의 거래에 대한 복식부기 전표."""

    entry_date: date
    summary: str
    source_type: SourceType
    source_id: int | None = None
    counterparty: str | None = None
    lines: list[JournalLine]

    @property
    def debit_total(self) -> int:
        return sum(line.amount_krw for line in self.lines if line.side == "차변")

    @property
    def credit_total(self) -> int:
        return sum(line.amount_krw for line in self.lines if line.side == "대변")

    @property
    def is_balanced(self) -> bool:
        return self.debit_total == self.credit_total


def counter_account_for(evidence_type: str | None) -> str:
    """증빙/결제 종류로 대변(상대) 계정을 결정한다."""
    if not evidence_type:
        return _DEFAULT_COUNTER_ACCOUNT
    return _COUNTER_ACCOUNT_BY_EVIDENCE.get(evidence_type, _DEFAULT_COUNTER_ACCOUNT)


def build_purchase_entry(
    *,
    entry_date: date,
    account_title: str,
    supply_value_krw: int,
    vat_krw: int,
    vat_creditable: bool,
    counter_account: str,
    summary: str,
    source_type: SourceType,
    source_id: int | None = None,
    counterparty: str | None = None,
) -> JournalEntry:
    """매입(비용) 거래를 전표로 변환한다.

    vat_creditable=False면 부가세를 비용 원가에 산입하고 부가세대급금 줄을 생략한다.
    """
    if supply_value_krw < 0 or vat_krw < 0:
        raise ValueError("공급가액/부가세는 음수가 될 수 없습니다.")

    total = supply_value_krw + vat_krw
    debit_lines: list[JournalLine] = []

    if vat_creditable and vat_krw > 0:
        debit_lines.append(
            JournalLine(
                side="차변",
                account_title=account_title,
                amount_krw=supply_value_krw,
                description=summary,
            )
        )
        debit_lines.append(
            JournalLine(
                side="차변",
                account_title=VAT_INPUT_ACCOUNT,
                amount_krw=vat_krw,
                description=summary,
            )
        )
    else:
        # 불공제: 부가세를 비용에 합산 (단일 차변 줄)
        debit_lines.append(
            JournalLine(
                side="차변",
                account_title=account_title,
                amount_krw=total,
                description=summary,
            )
        )

    credit_line = JournalLine(
        side="대변",
        account_title=counter_account,
        amount_krw=total,
        description=summary,
    )

    return JournalEntry(
        entry_date=entry_date,
        summary=summary,
        source_type=source_type,
        source_id=source_id,
        counterparty=counterparty,
        lines=[*debit_lines, credit_line],
    )


def build_sale_entry(
    *,
    entry_date: date,
    supply_value_krw: int,
    vat_krw: int,
    counter_account: str,
    summary: str,
    source_id: int | None = None,
    counterparty: str | None = None,
) -> JournalEntry:
    """매출 세금계산서를 전표로 변환한다.

    차) 외상매출금 합계 / 대) 매출 공급가액 + 부가세예수금 매출세액.
    """
    if supply_value_krw < 0 or vat_krw < 0:
        raise ValueError("공급가액/부가세는 음수가 될 수 없습니다.")

    total = supply_value_krw + vat_krw
    debit_line = JournalLine(
        side="차변",
        account_title=counter_account,
        amount_krw=total,
        description=summary,
    )
    credit_lines = [
        JournalLine(
            side="대변",
            account_title=SALES_ACCOUNT,
            amount_krw=supply_value_krw,
            description=summary,
        )
    ]
    if vat_krw > 0:
        credit_lines.append(
            JournalLine(
                side="대변",
                account_title=VAT_OUTPUT_ACCOUNT,
                amount_krw=vat_krw,
                description=summary,
            )
        )

    return JournalEntry(
        entry_date=entry_date,
        summary=summary,
        source_type="tax_invoice_sale",
        source_id=source_id,
        counterparty=counterparty,
        lines=[debit_line, *credit_lines],
    )


def build_entry_from_receipt(receipt: dict[str, Any]) -> JournalEntry | None:
    """승인된 영수증 dict 하나를 전표로 변환한다.

    Args:
        receipt: {"id", "transaction_date", "account_code", "parsed_data"} 형태.
                 parsed_data는 TaxDecision.model_dump() 형식.

    Returns:
        전표. 거래일·금액이 없어 변환 불가하면 None.
    """
    parsed = receipt.get("parsed_data") or {}
    calc = parsed.get("calculation_result") or {}
    supply = int(calc.get("supply_value_krw") or 0)
    vat = int(calc.get("vat_krw") or 0)
    if supply == 0 and vat == 0:
        return None

    entry_date = _coerce_date(receipt.get("transaction_date"))
    if entry_date is None:
        return None

    account_code = receipt.get("account_code") or parsed.get("account_code") or "미분류"
    evidence_type = parsed.get("evidence_type")
    merchant = _merchant_name(parsed)
    vat_creditable = parsed.get("vat_creditable") is True

    summary = merchant or account_code
    source_type: SourceType = "card" if evidence_type in ("card", "credit_card_slip") else "receipt"

    return build_purchase_entry(
        entry_date=entry_date,
        account_title=account_code,
        supply_value_krw=supply,
        vat_krw=vat,
        vat_creditable=vat_creditable,
        counter_account=counter_account_for(evidence_type),
        summary=summary,
        source_type=source_type,
        source_id=receipt.get("id"),
        counterparty=merchant,
    )


def build_entry_from_tax_invoice(invoice: dict[str, Any]) -> JournalEntry | None:
    """세금계산서 dict 하나를 전표로 변환한다 (매입/매출)."""
    supply = int(invoice.get("supply_value_krw") or 0)
    vat = int(invoice.get("vat_krw") or 0)
    if supply == 0 and vat == 0:
        return None

    entry_date = _coerce_date(invoice.get("issue_date"))
    if entry_date is None:
        return None

    direction = str(invoice.get("direction") or "").lower()
    source_id = invoice.get("id")

    if direction == "sale":
        counterparty = invoice.get("recipient_name")
        summary = counterparty or "매출 세금계산서"
        return build_sale_entry(
            entry_date=entry_date,
            supply_value_krw=supply,
            vat_krw=vat,
            counter_account="외상매출금",
            summary=summary,
            source_id=source_id,
            counterparty=counterparty,
        )

    # 기본: 매입
    counterparty = invoice.get("supplier_name")
    summary = counterparty or "매입 세금계산서"
    return build_purchase_entry(
        entry_date=entry_date,
        account_title="매입",
        supply_value_krw=supply,
        vat_krw=vat,
        vat_creditable=True,  # 적격 세금계산서 매입세액은 공제 가정
        counter_account="외상매입금",
        summary=summary,
        source_type="tax_invoice_purchase",
        source_id=source_id,
        counterparty=counterparty,
    )


def _merchant_name(parsed: dict[str, Any]) -> str | None:
    calc = parsed.get("calculation_result") or {}
    for key in ("merchant_name", "store_name", "supplier_name"):
        value = parsed.get(key) or calc.get(key)
        if value:
            return str(value)
    return None


def _coerce_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None

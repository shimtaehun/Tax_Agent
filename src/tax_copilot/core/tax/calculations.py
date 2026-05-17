from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel

from tax_copilot.core.schemas import ParsedReceipt


class VatCalculation(BaseModel):
    total_amount_krw: int
    supply_value_krw: int
    vat_amount_krw: int
    vat_rate_basis_points: int = 1000


def calculate_vat_amounts(receipt: ParsedReceipt) -> VatCalculation:
    """Calculate Korean VAT amounts deterministically from parsed receipt values."""
    if receipt.total_amount_krw is None and receipt.supply_value_krw is None:
        return VatCalculation(total_amount_krw=0, supply_value_krw=0, vat_amount_krw=0)

    if receipt.supply_value_krw is not None and receipt.vat_amount_krw is not None:
        total = receipt.total_amount_krw or receipt.supply_value_krw + receipt.vat_amount_krw
        return VatCalculation(
            total_amount_krw=total,
            supply_value_krw=receipt.supply_value_krw,
            vat_amount_krw=receipt.vat_amount_krw,
        )

    if receipt.total_amount_krw is not None:
        total_decimal = Decimal(receipt.total_amount_krw)
        supply = int((total_decimal / Decimal("1.1")).quantize(Decimal("1"), ROUND_HALF_UP))
        return VatCalculation(
            total_amount_krw=receipt.total_amount_krw,
            supply_value_krw=supply,
            vat_amount_krw=receipt.total_amount_krw - supply,
        )

    supply_value = receipt.supply_value_krw or 0
    vat = int((Decimal(supply_value) * Decimal("0.1")).quantize(Decimal("1"), ROUND_HALF_UP))
    return VatCalculation(
        total_amount_krw=supply_value + vat,
        supply_value_krw=supply_value,
        vat_amount_krw=vat,
    )

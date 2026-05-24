"""부가세 집계 순수 함수.

입력: parsed_data와 account_code를 담은 dict 목록 (ORM 의존 없음).
출력: creditable / non_creditable / by_account_code 집계 dict.
"""

from typing import Any


def aggregate_vat(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    """승인된 영수증 목록에서 부가세 공제/불공제를 집계한다.

    Args:
        receipts: [{"account_code": str, "parsed_data": dict}, ...]
                  parsed_data는 TaxDecision.model_dump() 형식.

    Returns:
        creditable, non_creditable, by_account_code 키를 갖는 dict.
    """
    cred_supply = 0
    cred_vat = 0
    cred_count = 0
    non_supply = 0
    non_vat = 0
    non_count = 0
    by_code: dict[str, dict[str, int]] = {}

    for r in receipts:
        parsed = r.get("parsed_data") or {}
        calc = parsed.get("calculation_result") or {}
        supply = int(calc.get("supply_value_krw") or 0)
        vat = int(calc.get("vat_krw") or 0)
        creditable = parsed.get("vat_creditable")
        account_code = r.get("account_code") or "미분류"

        if creditable is True:
            cred_supply += supply
            cred_vat += vat
            cred_count += 1
        elif creditable is False:
            non_supply += supply
            non_vat += vat
            non_count += 1

        # by_account_code: vat_creditable 값과 무관하게 전체 집계
        entry = by_code.setdefault(
            account_code,
            {"supply_value_krw": 0, "vat_krw": 0, "receipt_count": 0},
        )
        entry["supply_value_krw"] += supply
        entry["vat_krw"] += vat
        entry["receipt_count"] += 1

    return {
        "creditable": {
            "supply_value_krw": cred_supply,
            "vat_krw": cred_vat,
            "receipt_count": cred_count,
        },
        "non_creditable": {
            "supply_value_krw": non_supply,
            "vat_krw": non_vat,
            "receipt_count": non_count,
        },
        "by_account_code": [{"account_code": code, **vals} for code, vals in by_code.items()],
    }

"""누락 증빙 감지 순수 로직.

카드내역에는 있으나 대응하는 영수증(증빙)이 없는 결제를 가려낸다. 세무사가
매달 고객사에 "이 결제들 증빙 주세요"라고 요청할 목록의 근거가 된다.
core/ 레이어이므로 표준 라이브러리 + pydantic만 사용한다.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

DEFAULT_DATE_TOLERANCE_DAYS = 3


class CardCharge(BaseModel):
    """증빙 필요 여부를 따질 카드 결제 한 건."""

    id: int
    amount_krw: int
    transaction_date: date | None = None
    merchant_name: str | None = None


class ReceiptRef(BaseModel):
    """대응 가능한 영수증(증빙) 한 건."""

    id: int
    amount_krw: int
    transaction_date: date | None = None


def find_cards_missing_receipts(
    cards: list[CardCharge],
    receipts: list[ReceiptRef],
    *,
    date_tolerance_days: int = DEFAULT_DATE_TOLERANCE_DAYS,
) -> list[CardCharge]:
    """대응 영수증이 없는 카드 결제 목록을 반환한다.

    금액 정확 일치 + 거래일 오차 이내인 영수증을 1:1로 소비한다. 남은 카드 결제가
    '증빙 누락'이다.
    """
    remaining = list(receipts)
    missing: list[CardCharge] = []

    for card in cards:
        best_idx: int | None = None
        best_distance: int | None = None
        for idx, rcpt in enumerate(remaining):
            if rcpt.amount_krw != card.amount_krw:
                continue
            if card.transaction_date is None or rcpt.transaction_date is None:
                effective = date_tolerance_days + 1
            else:
                dist = abs((card.transaction_date - rcpt.transaction_date).days)
                if dist > date_tolerance_days:
                    continue
                effective = dist
            if best_distance is None or effective < best_distance:
                best_idx = idx
                best_distance = effective

        if best_idx is None:
            missing.append(card)
        else:
            remaining.pop(best_idx)

    return missing

"""삼중 대사(통장 ↔ 카드 ↔ 세금계산서) 순수 매칭 엔진.

통장 입출금 한 건을, 카드내역·세금계산서에서 도출한 '예상 현금흐름' 후보와
금액(정확 일치) + 거래일(허용 오차 이내)로 짝짓는다. 짝을 찾지 못한 통장 거래가
"근거 없는 입출금"이고, 통장에 없는 후보가 "통장 미반영" 항목이다.

core/ 레이어이므로 표준 라이브러리 + pydantic만 사용한다.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel

Direction = Literal["in", "out"]  # in=입금(매출 회수), out=출금(비용/매입 지급)

DEFAULT_DATE_TOLERANCE_DAYS = 3


class BankItem(BaseModel):
    """대사 대상 통장 거래 한 건."""

    id: int
    transaction_date: date | None = None
    deposit_krw: int = 0
    withdrawal_krw: int = 0

    @property
    def direction(self) -> Direction | None:
        if self.deposit_krw > 0:
            return "in"
        if self.withdrawal_krw > 0:
            return "out"
        return None

    @property
    def amount_krw(self) -> int:
        return self.deposit_krw if self.deposit_krw > 0 else self.withdrawal_krw


class ReconCandidate(BaseModel):
    """카드내역·세금계산서에서 도출한 예상 현금흐름 후보."""

    source_type: Literal["card", "tax_invoice_sale", "tax_invoice_purchase"]
    source_id: int
    amount_krw: int
    transaction_date: date | None = None
    direction: Direction
    label: str | None = None


class ReconMatch(BaseModel):
    bank_id: int
    source_type: str
    source_id: int
    amount_krw: int


class ReconResult(BaseModel):
    matches: list[ReconMatch]
    unmatched_bank_ids: list[int]  # 근거 없는 입출금
    unmatched_candidates: list[ReconCandidate]  # 통장 미반영 항목

    @property
    def matched_count(self) -> int:
        return len(self.matches)


def _date_distance(a: date | None, b: date | None) -> int | None:
    if a is None or b is None:
        return None
    return abs((a - b).days)


def reconcile(
    bank_items: list[BankItem],
    candidates: list[ReconCandidate],
    *,
    date_tolerance_days: int = DEFAULT_DATE_TOLERANCE_DAYS,
) -> ReconResult:
    """통장 거래와 후보를 그리디 매칭한다.

    각 통장 거래에 대해 같은 방향·동일 금액·거래일 오차 이내인 후보 중 거래일이
    가장 가까운 것을 매칭한다. 후보는 1:1로 한 번만 소비된다.
    """
    remaining = list(candidates)
    matches: list[ReconMatch] = []
    unmatched_bank: list[int] = []

    for bank in bank_items:
        direction = bank.direction
        if direction is None:
            unmatched_bank.append(bank.id)
            continue

        best_idx: int | None = None
        best_distance: int | None = None
        for idx, cand in enumerate(remaining):
            if cand.direction != direction or cand.amount_krw != bank.amount_krw:
                continue
            dist = _date_distance(bank.transaction_date, cand.transaction_date)
            if dist is not None and dist > date_tolerance_days:
                continue
            # 거래일 정보가 없으면 distance를 큰 값으로 취급(후순위).
            effective = dist if dist is not None else date_tolerance_days + 1
            if best_distance is None or effective < best_distance:
                best_idx = idx
                best_distance = effective

        if best_idx is None:
            unmatched_bank.append(bank.id)
            continue

        cand = remaining.pop(best_idx)
        matches.append(
            ReconMatch(
                bank_id=bank.id,
                source_type=cand.source_type,
                source_id=cand.source_id,
                amount_krw=bank.amount_krw,
            )
        )

    return ReconResult(
        matches=matches,
        unmatched_bank_ids=unmatched_bank,
        unmatched_candidates=remaining,
    )

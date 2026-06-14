"""카드사 결제내역 한 행의 정규화된 도메인 모델.

core/ 레이어이므로 외부 라이브러리 없음. 영수증의 ParsedReceipt(pydantic)와 달리
세금계산서 import 계층(core/tax/invoice_parser.ParsedTaxInvoice)의 frozen dataclass
관례를 따른다 — 파일 import 결과는 불변 값 객체로 다룬다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import Any


@dataclass(frozen=True)
class StatementRow:
    """카드사 엑셀 결제목록의 한 행 = 하나의 거래."""

    transaction_date: date | None
    merchant_name: str | None = None
    approval_no: str | None = None  # 승인번호 (행 단위 중복 방지 키)
    total_amount_krw: int | None = None

    transaction_time: time | None = None
    card_no_masked: str | None = None  # 카드번호 뒤 4자리 등 마스킹 값
    supply_value_krw: int | None = None  # 공급가액 (부가세 제외)
    vat_krw: int | None = None  # 부가세
    installment_months: int | None = None  # 할부 개월 (일시불은 0/None)
    category: str | None = None  # 가맹점 업종/분류
    currency: str = "KRW"
    cancelled: bool = False  # 취소/환불 건 여부

    raw: dict[str, Any] = field(default_factory=dict)  # 원본 행 (감사 추적용)

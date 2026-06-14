"""파싱된 카드 결제내역을 DB에 적재하는 파이프라인.

세금계산서 import 엔드포인트의 적재/중복방지 로직과 동일한 패턴을 재사용 가능한
함수로 추출했다. 추후 추가될 업로드 API가 이 함수를 호출한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tax_copilot.core.statements.schemas import StatementRow
from tax_copilot.core.tax.account_classifier import classify_account_code
from tax_copilot.infra.db.models.card_transaction import CardTransaction

# 카드 결제내역은 신용카드 매출전표 증빙으로 본다.
_STATEMENT_EVIDENCE_TYPE = "credit_card_slip"


@dataclass(frozen=True)
class StatementIngestResult:
    """적재 결과 요약."""

    imported: int
    skipped: int

    @property
    def total(self) -> int:
        return self.imported + self.skipped


async def ingest_statement_rows(
    db: AsyncSession,
    rows: list[StatementRow],
    *,
    tenant_id: int,
    client_company_id: int,
    uploaded_by: int,
    source_filename: str,
    card_company: str,
) -> StatementIngestResult:
    """StatementRow 리스트를 card_transactions 테이블에 적재한다.

    승인번호가 있는 행은 (tenant, 거래처, 승인번호) 기준으로 중복을 건너뛴다.
    승인번호가 없는 행은 중복 판별 불가이므로 그대로 적재한다.
    """
    imported = 0
    skipped = 0

    for row in rows:
        if row.approval_no:
            existing = await db.execute(
                select(CardTransaction.id).where(
                    CardTransaction.tenant_id == tenant_id,
                    CardTransaction.client_company_id == client_company_id,
                    CardTransaction.approval_no == row.approval_no,
                )
            )
            if existing.scalar_one_or_none() is not None:
                skipped += 1
                continue

        account_code, _ = classify_account_code(row.merchant_name, _STATEMENT_EVIDENCE_TYPE)
        db.add(
            CardTransaction(
                tenant_id=tenant_id,
                client_company_id=client_company_id,
                uploaded_by=uploaded_by,
                card_company=card_company,
                source_filename=source_filename,
                account_code=account_code,
                transaction_date=row.transaction_date,
                transaction_time=row.transaction_time,
                merchant_name=row.merchant_name,
                approval_no=row.approval_no,
                card_no_masked=row.card_no_masked,
                total_amount_krw=row.total_amount_krw,
                supply_value_krw=row.supply_value_krw,
                vat_krw=row.vat_krw,
                installment_months=row.installment_months,
                category=row.category,
                currency=row.currency,
                cancelled=row.cancelled,
                raw_data=row.raw or None,
            )
        )
        imported += 1

    await db.commit()
    return StatementIngestResult(imported=imported, skipped=skipped)

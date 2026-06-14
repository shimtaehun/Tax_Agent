from fastapi import APIRouter

from tax_copilot.api.v1.account_rules import router as account_rules_router
from tax_copilot.api.v1.auth import router as auth_router
from tax_copilot.api.v1.deadlines import router as deadlines_router
from tax_copilot.api.v1.journal import router as journal_router
from tax_copilot.api.v1.monthly_reports import router as monthly_reports_router
from tax_copilot.api.v1.portal import router as portal_router
from tax_copilot.api.v1.receipts import router as receipts_router
from tax_copilot.api.v1.reviews import router as reviews_router
from tax_copilot.api.v1.risk import router as risk_router
from tax_copilot.api.v1.statements import router as statements_router
from tax_copilot.api.v1.tax_invoices import router as tax_invoices_router
from tax_copilot.api.v1.vat import router as vat_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(account_rules_router)
v1_router.include_router(receipts_router)
v1_router.include_router(portal_router)
v1_router.include_router(reviews_router)
v1_router.include_router(vat_router)
v1_router.include_router(risk_router)
v1_router.include_router(deadlines_router)
v1_router.include_router(journal_router)
v1_router.include_router(tax_invoices_router)
v1_router.include_router(statements_router)
v1_router.include_router(monthly_reports_router)

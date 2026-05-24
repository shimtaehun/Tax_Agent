from fastapi import APIRouter

from tax_copilot.api.v1.auth import router as auth_router
from tax_copilot.api.v1.deadlines import router as deadlines_router
from tax_copilot.api.v1.receipts import router as receipts_router
from tax_copilot.api.v1.reviews import router as reviews_router
from tax_copilot.api.v1.risk import router as risk_router
from tax_copilot.api.v1.vat import router as vat_router

v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(auth_router)
v1_router.include_router(receipts_router)
v1_router.include_router(reviews_router)
v1_router.include_router(vat_router)
v1_router.include_router(risk_router)
v1_router.include_router(deadlines_router)

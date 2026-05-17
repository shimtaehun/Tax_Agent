import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tax_copilot.api.errors import register_exception_handlers
from tax_copilot.api.v1.auth import router as auth_router
from tax_copilot.api.v1.receipts import router as receipts_router
from tax_copilot.core.config import settings
from tax_copilot.core.logging import configure_logging, request_id_var

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    configure_logging(json_logs=not settings.debug)
    logger.info("startup", version="0.1.0")
    yield
    logger.info("shutdown")


app = FastAPI(
    title="Tax-Copilot",
    version="0.1.0",
    lifespan=lifespan,
)

register_exception_handlers(app)

app.include_router(auth_router, prefix="/v1")
app.include_router(receipts_router, prefix="/v1")


@app.middleware("http")
async def request_id_middleware(request: Request, call_next: object) -> object:
    rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_var.set(rid)
    try:
        response = await call_next(request)  # type: ignore[operator]
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        request_id_var.reset(token)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})

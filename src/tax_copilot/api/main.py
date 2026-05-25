import uuid
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

from tax_copilot import __version__
from tax_copilot.agents.graph import build_graph
from tax_copilot.api.errors import register_exception_handlers
from tax_copilot.api.v1 import v1_router
from tax_copilot.core.config import settings
from tax_copilot.core.logging import configure_logging, request_id_var

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Configure process-wide services for the API lifecycle."""
    configure_logging(json_logs=not settings.debug)

    # PostgreSQL Checkpointer: graph 실행 상태를 DB에 저장, HITL resume 지원
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(settings.checkpointer_url) as checkpointer:
        await checkpointer.setup()  # checkpoint 테이블 초기화 (멱등)
        app.state.graph = build_graph(checkpointer=checkpointer)
        logger.info("startup", version=__version__)
        yield
        logger.info("shutdown")


app = FastAPI(
    title="Tax-Copilot",
    version=__version__,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        settings.frontend_url,
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)
app.include_router(v1_router)


@app.middleware("http")
async def request_id_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        request_id_var.reset(token)


@app.get("/healthz", include_in_schema=False)
async def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})

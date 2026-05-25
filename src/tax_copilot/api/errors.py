from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tax_copilot.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    DuplicateReceiptError,
    ExternalServiceError,
    ExtractionFailedError,
    LawCorpusVersionMismatch,
    TaxCopilotError,
    ValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Register API error handlers mapping domain exceptions to HTTP responses."""

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(AuthenticationError)
    async def auth_error_handler(request: Request, exc: AuthenticationError) -> JSONResponse:
        return JSONResponse(status_code=401, content={"detail": str(exc)})

    @app.exception_handler(AuthorizationError)
    async def authz_error_handler(request: Request, exc: AuthorizationError) -> JSONResponse:
        return JSONResponse(status_code=403, content={"detail": str(exc)})

    @app.exception_handler(DuplicateReceiptError)
    async def duplicate_receipt_handler(
        request: Request, exc: DuplicateReceiptError
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ExtractionFailedError)
    async def extraction_failed_handler(
        request: Request, exc: ExtractionFailedError
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(ExternalServiceError)
    async def external_service_handler(request: Request, exc: ExternalServiceError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(LawCorpusVersionMismatch)
    async def corpus_version_handler(
        request: Request, exc: LawCorpusVersionMismatch
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(TaxCopilotError)
    async def tax_copilot_error_handler(request: Request, exc: TaxCopilotError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

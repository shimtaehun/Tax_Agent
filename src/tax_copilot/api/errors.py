from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from tax_copilot.core.exceptions import (
    DuplicateReceiptError,
    ExternalServiceError,
    ExtractionFailedError,
    LawCorpusVersionMismatch,
    TaxCopilotError,
    ValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValidationError)
    async def validation_error_handler(request: Request, exc: ValidationError) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    @app.exception_handler(DuplicateReceiptError)
    async def duplicate_handler(request: Request, exc: DuplicateReceiptError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    @app.exception_handler(ExtractionFailedError)
    async def extraction_handler(request: Request, exc: ExtractionFailedError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(LawCorpusVersionMismatch)
    async def corpus_mismatch_handler(
        request: Request, exc: LawCorpusVersionMismatch
    ) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(ExternalServiceError)
    async def external_error_handler(request: Request, exc: ExternalServiceError) -> JSONResponse:
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(TaxCopilotError)
    async def base_error_handler(request: Request, exc: TaxCopilotError) -> JSONResponse:
        return JSONResponse(status_code=500, content={"detail": str(exc)})

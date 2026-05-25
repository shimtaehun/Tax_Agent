class TaxCopilotError(Exception):
    """Base exception for all domain errors."""


class ValidationError(TaxCopilotError):
    """Input failed domain validation. Maps to HTTP 400."""


class DuplicateReceiptError(TaxCopilotError):
    """Receipt already processed for this tenant. Maps to HTTP 409."""


class ExtractionFailedError(TaxCopilotError):
    """Vision extraction returned unusable output. Maps to HTTP 422."""


class StorageError(TaxCopilotError):
    """File storage operation failed."""


class ExternalServiceError(TaxCopilotError):
    """External API call failed (Gemini, Qdrant, etc.). Maps to HTTP 503."""


class LawCorpusVersionMismatch(TaxCopilotError):
    """as_of_date not covered by current corpus. Maps to HTTP 503."""


class HumanReviewRequired(TaxCopilotError):
    """Decision requires human approval — not an error, just a signal."""


class AuthenticationError(TaxCopilotError):
    """Invalid credentials or missing token. Maps to HTTP 401."""


class AuthorizationError(TaxCopilotError):
    """Caller lacks required role or tenant scope. Maps to HTTP 403."""

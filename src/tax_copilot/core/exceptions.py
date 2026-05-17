class TaxCopilotError(Exception):
    """Base exception for all domain errors."""


class ValidationError(TaxCopilotError):
    """Invalid input — HTTP 400."""


class DuplicateReceiptError(TaxCopilotError):
    """Receipt already processed for this tenant — HTTP 409."""


class ExtractionFailedError(TaxCopilotError):
    """Vision extraction returned unusable output — HTTP 422."""


class LawCorpusVersionMismatch(TaxCopilotError):
    """Requested as_of_date not covered by current corpus — HTTP 503."""


class HumanReviewRequiredError(TaxCopilotError):
    """Decision needs human approval (not a failure)."""


class ExternalServiceError(TaxCopilotError):
    """Upstream service (Gemini, Qdrant, etc.) is unavailable — HTTP 502."""

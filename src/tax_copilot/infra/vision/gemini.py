from tax_copilot.core.config import settings
from tax_copilot.core.exceptions import ExternalServiceError
from tax_copilot.core.schemas import ParsedReceipt


class GeminiReceiptExtractor:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else settings.gemini_api_key

    def extract(self, *, file_path: str, mime_type: str) -> ParsedReceipt:
        if not self.api_key:
            raise ExternalServiceError("Gemini API key is not configured")
        raise ExternalServiceError("Gemini Vision extraction adapter is not implemented yet")

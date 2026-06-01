from pydantic import BaseModel

from tax_copilot.schemas.receipts import ReceiptStatusResponse


class PortalDashboardResponse(BaseModel):
    client_company_id: int
    total: int
    by_status: dict[str, int]
    recent_receipts: list[ReceiptStatusResponse]

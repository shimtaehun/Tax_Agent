from datetime import date

from pydantic import BaseModel


class MonthlyReportResponse(BaseModel):
    client_company_id: int
    month: str
    from_date: date
    to_date: date
    processed_receipt_count: int
    pending_receipt_count: int
    purchase_invoice_count: int
    sales_invoice_count: int
    receipt_input_vat_krw: int
    purchase_invoice_vat_krw: int
    sales_invoice_vat_krw: int
    total_input_vat_krw: int
    estimated_vat_payable_krw: int
    next_deadline: dict | None

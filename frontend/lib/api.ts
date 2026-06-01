const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function authHeaders(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function handleUnauthorized(status: number): void {
  if (status === 401) {
    localStorage.removeItem("token");
    window.location.href = "/login";
  }
}

async function parseError(res: Response, fallback: string): Promise<string> {
  try {
    const body = await res.json();
    return body.detail ?? fallback;
  } catch {
    return fallback;
  }
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch(`${BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) throw new Error(await parseError(res, "로그인 실패"));
  const data = await res.json();
  localStorage.setItem("token", data.access_token);
}

export function logout(): void {
  localStorage.removeItem("token");
  window.location.href = "/login";
}

export function isLoggedIn(): boolean {
  if (typeof window === "undefined") return false;
  return !!localStorage.getItem("token");
}

export interface ReviewItem {
  receipt_id: number;
  original_filename: string;
  langgraph_thread_id: string;
  created_at: string;
}

export interface ReviewHistoryItem {
  receipt_id: number;
  original_filename: string;
  status: "APPROVED" | "REJECTED";
  reviewed_by: number | null;
  reviewed_at: string | null;
  review_comment: string | null;
  transaction_date: string | null;
  account_code: string | null;
  created_at: string;
}

export interface ReceiptStatus {
  receipt_id: number;
  status: string;
  original_filename: string;
  mime_type: string;
  file_size_bytes: number;
  client_company_id: number;
  uploaded_by: number;
  transaction_date: string | null;
  parsed_data: Record<string, unknown> | null;
  langgraph_thread_id: string | null;
  attempt_number: number;
  error_message: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
  review_comment: string | null;
  account_code: string | null;
  account_code_reason: string | null;
  duplicate_suspect: boolean;
  duplicate_receipt_ids: number[];
  created_at: string;
  updated_at: string;
}

export interface ReceiptListResponse {
  items: ReceiptStatus[];
  total: number;
}

export interface TaxInvoiceItem {
  id: number;
  client_company_id: number;
  direction: "SALE" | "PURCHASE";
  approval_no: string;
  issue_date: string;
  supplier_business_no: string | null;
  supplier_name: string | null;
  recipient_business_no: string | null;
  recipient_name: string | null;
  item_name: string | null;
  supply_value_krw: number;
  vat_krw: number;
  total_amount_krw: number;
  source_filename: string;
  created_at: string;
}

export interface TaxInvoiceListResponse {
  items: TaxInvoiceItem[];
  total: number;
}

export interface MonthlyReport {
  client_company_id: number;
  month: string;
  from_date: string;
  to_date: string;
  processed_receipt_count: number;
  pending_receipt_count: number;
  purchase_invoice_count: number;
  sales_invoice_count: number;
  receipt_input_vat_krw: number;
  purchase_invoice_vat_krw: number;
  sales_invoice_vat_krw: number;
  total_input_vat_krw: number;
  estimated_vat_payable_krw: number;
  next_deadline: { id: number; tax_type: string; due_date: string; description: string } | null;
}

export async function getPendingReviews(): Promise<ReviewItem[]> {
  const res = await fetch(`${BASE}/api/v1/reviews/pending`, {
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "목록 조회 실패"));
  return res.json();
}

export async function getReviewHistory(): Promise<ReviewHistoryItem[]> {
  const res = await fetch(`${BASE}/api/v1/reviews/history`, {
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "히스토리 조회 실패"));
  return res.json();
}

export async function getReceipts(status?: string): Promise<ReceiptListResponse> {
  const url = status
    ? `${BASE}/api/v1/receipts?status=${encodeURIComponent(status)}&limit=100`
    : `${BASE}/api/v1/receipts?limit=100`;
  const res = await fetch(url, { headers: authHeaders() });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "영수증 목록 조회 실패"));
  return res.json();
}

export async function getTaxInvoices(
  clientCompanyId = 1,
  fromDate?: string,
  toDate?: string
): Promise<TaxInvoiceListResponse> {
  const params = new URLSearchParams({ client_company_id: String(clientCompanyId), limit: "200" });
  if (fromDate) params.set("from_date", fromDate);
  if (toDate) params.set("to_date", toDate);
  const res = await fetch(`${BASE}/api/v1/tax-invoices?${params.toString()}`, {
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "세금계산서 목록 조회 실패"));
  return res.json();
}

export async function uploadTaxInvoices(
  file: File,
  direction: "SALE" | "PURCHASE",
  clientCompanyId = 1
): Promise<{ imported_count: number; skipped_count: number; items: TaxInvoiceItem[] }> {
  const form = new FormData();
  form.append("file", file);
  const params = new URLSearchParams({
    client_company_id: String(clientCompanyId),
    invoice_direction: direction,
  });
  const res = await fetch(`${BASE}/api/v1/tax-invoices/upload?${params.toString()}`, {
    method: "POST",
    headers: authHeaders(),
    body: form,
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "세금계산서 업로드 실패"));
  return res.json();
}

export async function getTaxInvoice(invoiceId: number): Promise<TaxInvoiceItem> {
  const res = await fetch(`${BASE}/api/v1/tax-invoices/${invoiceId}`, {
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "세금계산서 조회 실패"));
  return res.json();
}

export async function updateTaxInvoice(
  invoiceId: number,
  data: Partial<Omit<TaxInvoiceItem, "id" | "client_company_id" | "source_filename" | "created_at">>
): Promise<TaxInvoiceItem> {
  const res = await fetch(`${BASE}/api/v1/tax-invoices/${invoiceId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "세금계산서 수정 실패"));
  return res.json();
}

export async function deleteTaxInvoice(invoiceId: number): Promise<void> {
  const res = await fetch(`${BASE}/api/v1/tax-invoices/${invoiceId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "세금계산서 삭제 실패"));
}

export async function getMonthlyReport(clientCompanyId: number, month: string): Promise<MonthlyReport> {
  const params = new URLSearchParams({ client_company_id: String(clientCompanyId), month });
  const res = await fetch(`${BASE}/api/v1/monthly-reports?${params.toString()}`, {
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "월별 리포트 조회 실패"));
  return res.json();
}

export async function downloadMonthlyReportHtml(clientCompanyId: number, month: string): Promise<void> {
  const params = new URLSearchParams({ client_company_id: String(clientCompanyId), month });
  const res = await fetch(`${BASE}/api/v1/monthly-reports/html?${params.toString()}`, {
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "월별 리포트 다운로드 실패"));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `monthly-report-${month}.html`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function getReceiptStatus(receiptId: number): Promise<ReceiptStatus> {
  const res = await fetch(`${BASE}/api/v1/receipts/${receiptId}`, {
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "영수증 조회 실패"));
  return res.json();
}

export interface CitationItem {
  chunk_id: string;
  law_name: string;
  article_no: string | null;
  paragraph_no: string | null;
  effective_from: string;
  effective_to: string | null;
  quoted_text: string;
}

export interface ExplanationResponse {
  receipt_id: number;
  status: string;
  decision: {
    vat_creditable: boolean | null;
    expense_deductible: boolean | null;
    account_code: string | null;
    account_code_reason: string | null;
    evidence_type: string;
    evidence_status: string;
    confidence: number;
    calculation_result: Record<string, unknown> | null;
    human_approved: boolean | null;
    human_comment: string | null;
  } | null;
  citations: CitationItem[];
  risk_flags: string[];
  audit_trail: Array<{
    event_type: string;
    actor_user_id: number | null;
    created_at: string;
    payload: Record<string, unknown> | null;
  }>;
}

export interface CommentItem {
  id: number;
  receipt_id: number;
  author_id: number;
  body: string;
  created_at: string;
}

export async function getReceiptExplanation(receiptId: number): Promise<ExplanationResponse> {
  const res = await fetch(`${BASE}/api/v1/receipts/${receiptId}/explanation`, {
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "판단 근거 조회 실패"));
  return res.json();
}

export async function getReceiptComments(receiptId: number): Promise<CommentItem[]> {
  const res = await fetch(`${BASE}/api/v1/receipts/${receiptId}/comments`, {
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "코멘트 조회 실패"));
  const data = await res.json();
  return data.items;
}

export async function createReceiptComment(receiptId: number, body: string): Promise<CommentItem> {
  const res = await fetch(`${BASE}/api/v1/receipts/${receiptId}/comments`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ body }),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "코멘트 등록 실패"));
  return res.json();
}

export async function retryReceipt(receiptId: number): Promise<ReceiptStatus> {
  const res = await fetch(`${BASE}/api/v1/receipts/${receiptId}/retry`, {
    method: "POST",
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "재처리 요청 실패"));
  return res.json();
}

export async function cancelReceipt(receiptId: number): Promise<ReceiptStatus> {
  const res = await fetch(`${BASE}/api/v1/receipts/${receiptId}/cancel`, {
    method: "POST",
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "취소 실패"));
  return res.json();
}

export async function downloadAuditCsv(receiptId: number): Promise<void> {
  const res = await fetch(`${BASE}/api/v1/receipts/${receiptId}/audit.csv`, {
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "감사 로그 다운로드 실패"));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `receipt-${receiptId}-audit.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function uploadReceipt(
  file: File,
  clientCompanyId: number = 1
): Promise<{ receipt_id: number; status: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(
    `${BASE}/api/v1/receipts?client_company_id=${clientCompanyId}`,
    {
      method: "POST",
      headers: authHeaders(),
      body: form,
    }
  );
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "업로드 실패"));
  return res.json();
}

export async function updateReceiptReview(
  id: number,
  data: { account_code?: string; review_comment?: string }
): Promise<ReceiptStatus> {
  const res = await fetch(`${BASE}/api/v1/receipts/${id}/review`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify(data),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "수정 실패"));
  return res.json();
}

export async function deleteReceipt(id: number): Promise<void> {
  const res = await fetch(`${BASE}/api/v1/receipts/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "삭제 실패"));
}

export async function decide(
  receiptId: number,
  approved: boolean,
  comment: string
): Promise<{ status: string; message: string }> {
  const res = await fetch(`${BASE}/api/v1/reviews/${receiptId}/decide`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ approved, comment }),
  });
  handleUnauthorized(res.status);
  if (!res.ok) throw new Error(await parseError(res, "처리 실패"));
  return res.json();
}

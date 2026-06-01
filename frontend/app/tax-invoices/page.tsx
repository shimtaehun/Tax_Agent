"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import Sidebar from "../components/Sidebar";
import StatCard from "../components/StatCard";
import {
  deleteTaxInvoice,
  getTaxInvoices,
  isLoggedIn,
  updateTaxInvoice,
  uploadTaxInvoices,
  TaxInvoiceItem,
} from "../../lib/api";

const DIRECTION_LABEL: Record<string, string> = {
  SALE: "매출",
  PURCHASE: "매입",
};

const money = (value: number) => `${value.toLocaleString("ko-KR")}원`;

export default function TaxInvoicesPage() {
  const [items, setItems] = useState<TaxInvoiceItem[]>([]);
  const [direction, setDirection] = useState<"SALE" | "PURCHASE">("PURCHASE");
  const [filter, setFilter] = useState<"ALL" | "PURCHASE" | "SALE">("ALL");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<TaxInvoiceItem | null>(null);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState("");
  const [form, setForm] = useState({
    direction: "PURCHASE" as "SALE" | "PURCHASE",
    approval_no: "",
    issue_date: "",
    supplier_business_no: "",
    supplier_name: "",
    recipient_business_no: "",
    recipient_name: "",
    item_name: "",
    supply_value_krw: "0",
    vat_krw: "0",
    total_amount_krw: "0",
  });
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      window.location.href = "/login";
      return;
    }
    load();
  }, []);

  async function load() {
    setLoading(true);
    setError("");
    try {
      const res = await getTaxInvoices();
      setItems(res.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "세금계산서 조회 실패");
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMessage("");
    setError("");
    try {
      const res = await uploadTaxInvoices(file, direction);
      setMessage(`가져오기 완료: ${res.imported_count}건, 중복 건너뜀: ${res.skipped_count}건`);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "세금계산서 업로드 실패");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  function openDetail(item: TaxInvoiceItem) {
    setSelected(item);
    setEditing(false);
    setActionError("");
    setForm({
      direction: item.direction,
      approval_no: item.approval_no,
      issue_date: item.issue_date,
      supplier_business_no: item.supplier_business_no ?? "",
      supplier_name: item.supplier_name ?? "",
      recipient_business_no: item.recipient_business_no ?? "",
      recipient_name: item.recipient_name ?? "",
      item_name: item.item_name ?? "",
      supply_value_krw: String(item.supply_value_krw),
      vat_krw: String(item.vat_krw),
      total_amount_krw: String(item.total_amount_krw),
    });
  }

  function closeDetail() {
    setSelected(null);
    setEditing(false);
    setActionError("");
  }

  function updateForm(name: string, value: string) {
    setForm((prev) => ({ ...prev, [name]: value }));
  }

  async function handleSave() {
    if (!selected) return;
    setSaving(true);
    setActionError("");
    try {
      const updated = await updateTaxInvoice(selected.id, {
        direction: form.direction,
        approval_no: form.approval_no,
        issue_date: form.issue_date,
        supplier_business_no: form.supplier_business_no,
        supplier_name: form.supplier_name,
        recipient_business_no: form.recipient_business_no,
        recipient_name: form.recipient_name,
        item_name: form.item_name,
        supply_value_krw: Number(form.supply_value_krw),
        vat_krw: Number(form.vat_krw),
        total_amount_krw: Number(form.total_amount_krw),
      });
      setSelected(updated);
      setItems((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setEditing(false);
      setMessage("세금계산서를 수정했습니다.");
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "세금계산서 수정 실패");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selected) return;
    setDeleting(true);
    setActionError("");
    try {
      await deleteTaxInvoice(selected.id);
      setItems((prev) => prev.filter((item) => item.id !== selected.id));
      closeDetail();
      setMessage("세금계산서를 삭제했습니다.");
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "세금계산서 삭제 실패");
    } finally {
      setDeleting(false);
    }
  }

  return (
    <main className="shell">
      <Sidebar active="tax-invoices" />

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>세금계산서 관리</h1>
            <p>홈택스에서 내려받은 전자세금계산서 XML/CSV를 매출·매입 자료로 가져옵니다.</p>
          </div>
          <div className="toolbar">
            <select value={direction} onChange={(e) => setDirection(e.target.value as "SALE" | "PURCHASE")}>
              <option value="PURCHASE">매입</option>
              <option value="SALE">매출</option>
            </select>
            <button onClick={() => fileRef.current?.click()} disabled={uploading}>
              {uploading ? "가져오는 중..." : "XML/CSV 업로드"}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".xml,.csv"
              style={{ display: "none" }}
              onChange={handleUpload}
            />
          </div>
        </header>

        {message && <p style={{ color: "var(--success)", marginTop: 16 }}>{message}</p>}
        {error && <p style={{ color: "var(--danger)", marginTop: 16 }}>{error}</p>}

        <section className="summaryGrid">
          <StatCard icon="receipt" tone="primary" hero label="전체 세금계산서" value={`${items.length.toLocaleString("ko-KR")}건`} />
          <StatCard icon="fileIn" tone="info" label="매입세액" value={money(items.filter((i) => i.direction === "PURCHASE").reduce((sum, i) => sum + i.vat_krw, 0))} />
          <StatCard icon="fileOut" tone="success" label="매출세액" value={money(items.filter((i) => i.direction === "SALE").reduce((sum, i) => sum + i.vat_krw, 0))} />
        </section>

        {loading ? (
          <div className="loader">불러오는 중...</div>
        ) : items.length === 0 ? (
          <div className="emptyState">가져온 세금계산서가 없습니다.</div>
        ) : (
          <>
            <div className="tableHead">
              <div className="segmented">
                <button className={filter === "ALL" ? "on" : ""} onClick={() => setFilter("ALL")}>전체</button>
                <button className={filter === "PURCHASE" ? "on" : ""} onClick={() => setFilter("PURCHASE")}>매입</button>
                <button className={filter === "SALE" ? "on" : ""} onClick={() => setFilter("SALE")}>매출</button>
              </div>
              <span style={{ fontSize: 13, color: "var(--muted)", fontWeight: 600 }}>
                {(filter === "ALL" ? items : items.filter((i) => i.direction === filter)).length.toLocaleString("ko-KR")}건
              </span>
            </div>
            <table className="dataTable">
            <thead>
              <tr>
                {["구분", "작성일자", "승인번호", "거래처", "품목", "공급가액", "세액", "합계"].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(filter === "ALL" ? items : items.filter((i) => i.direction === filter)).map((item) => (
                <tr key={item.id} onClick={() => openDetail(item)} style={{ cursor: "pointer" }}>
                  <td>
                    <span className={`badge ${item.direction === "SALE" ? "badge-success" : "badge-info"}`}>
                      {DIRECTION_LABEL[item.direction]}
                    </span>
                  </td>
                  <td>{item.issue_date}</td>
                  <td>{item.approval_no}</td>
                  <td>{item.direction === "PURCHASE" ? item.supplier_name : item.recipient_name}</td>
                  <td>{item.item_name ?? "-"}</td>
                  <td>{money(item.supply_value_krw)}</td>
                  <td>{money(item.vat_krw)}</td>
                  <td>{money(item.total_amount_krw)}</td>
                </tr>
              ))}
            </tbody>
            </table>
          </>
        )}
      </section>

      {selected && (
        <div className="modalBackdrop" onClick={closeDetail}>
          <div className="modalPanel" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 16, marginBottom: 20 }}>
              <div>
                <p style={{ color: "var(--muted)", fontSize: 12, margin: 0 }}>
                  {DIRECTION_LABEL[selected.direction]} 세금계산서
                </p>
                <h2 style={{ fontSize: 20, marginTop: 4 }}>{selected.approval_no}</h2>
              </div>
              <button className="secondary" onClick={closeDetail}>닫기</button>
            </div>

            {actionError && <p style={{ color: "var(--danger)", marginBottom: 12 }}>{actionError}</p>}

            <div className="formGrid">
              <label>
                구분
                {editing ? (
                  <select value={form.direction} onChange={(e) => updateForm("direction", e.target.value)}>
                    <option value="PURCHASE">매입</option>
                    <option value="SALE">매출</option>
                  </select>
                ) : <strong>{DIRECTION_LABEL[selected.direction]}</strong>}
              </label>
              <label>
                작성일자
                {editing ? (
                  <input type="date" value={form.issue_date} onChange={(e) => updateForm("issue_date", e.target.value)} />
                ) : <strong>{selected.issue_date}</strong>}
              </label>
              <label className="wide">
                승인번호
                {editing ? (
                  <input value={form.approval_no} onChange={(e) => updateForm("approval_no", e.target.value)} />
                ) : <strong>{selected.approval_no}</strong>}
              </label>
              <label>
                공급자 등록번호
                {editing ? (
                  <input value={form.supplier_business_no} onChange={(e) => updateForm("supplier_business_no", e.target.value)} />
                ) : <strong>{selected.supplier_business_no ?? "-"}</strong>}
              </label>
              <label>
                공급자
                {editing ? (
                  <input value={form.supplier_name} onChange={(e) => updateForm("supplier_name", e.target.value)} />
                ) : <strong>{selected.supplier_name ?? "-"}</strong>}
              </label>
              <label>
                공급받는자 등록번호
                {editing ? (
                  <input value={form.recipient_business_no} onChange={(e) => updateForm("recipient_business_no", e.target.value)} />
                ) : <strong>{selected.recipient_business_no ?? "-"}</strong>}
              </label>
              <label>
                공급받는자
                {editing ? (
                  <input value={form.recipient_name} onChange={(e) => updateForm("recipient_name", e.target.value)} />
                ) : <strong>{selected.recipient_name ?? "-"}</strong>}
              </label>
              <label className="wide">
                품목
                {editing ? (
                  <input value={form.item_name} onChange={(e) => updateForm("item_name", e.target.value)} />
                ) : <strong>{selected.item_name ?? "-"}</strong>}
              </label>
              <label>
                공급가액
                {editing ? (
                  <input type="number" min="0" value={form.supply_value_krw} onChange={(e) => updateForm("supply_value_krw", e.target.value)} />
                ) : <strong>{money(selected.supply_value_krw)}</strong>}
              </label>
              <label>
                세액
                {editing ? (
                  <input type="number" min="0" value={form.vat_krw} onChange={(e) => updateForm("vat_krw", e.target.value)} />
                ) : <strong>{money(selected.vat_krw)}</strong>}
              </label>
              <label>
                합계금액
                {editing ? (
                  <input type="number" min="0" value={form.total_amount_krw} onChange={(e) => updateForm("total_amount_krw", e.target.value)} />
                ) : <strong>{money(selected.total_amount_krw)}</strong>}
              </label>
              <label>
                원본 파일
                <strong>{selected.source_filename}</strong>
              </label>
            </div>

            <div className="actions" style={{ marginTop: 24 }}>
              {editing ? (
                <>
                  <button className="secondary" onClick={() => openDetail(selected)} disabled={saving}>취소</button>
                  <button onClick={handleSave} disabled={saving}>{saving ? "저장 중..." : "저장"}</button>
                </>
              ) : (
                <>
                  <button className="btn-ghost-danger" onClick={handleDelete} disabled={deleting}>
                    {deleting ? "삭제 중..." : "삭제"}
                  </button>
                  <button onClick={() => setEditing(true)}>수정</button>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

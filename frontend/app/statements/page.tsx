"use client";

import { ChangeEvent, useEffect, useRef, useState } from "react";
import Sidebar from "../components/Sidebar";
import StatCard from "../components/StatCard";
import {
  getStatements,
  isLoggedIn,
  uploadStatement,
  StatementTransactionItem,
} from "../../lib/api";

const CARD_LABEL: Record<string, string> = {
  hyundai: "현대카드",
};

const cardLabel = (code: string) => CARD_LABEL[code] ?? code;
const money = (value: number | null) => `${(value ?? 0).toLocaleString("ko-KR")}원`;

const CARD_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "자동 판별" },
  { value: "hyundai", label: "현대카드" },
];

export default function StatementsPage() {
  const [items, setItems] = useState<StatementTransactionItem[]>([]);
  const [cardCompany, setCardCompany] = useState("");
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<StatementTransactionItem | null>(null);
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
      const res = await getStatements();
      setItems(res.items);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "카드내역 조회 실패");
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
      const res = await uploadStatement(file, cardCompany || undefined);
      setMessage(
        `${cardLabel(res.card_company)} 가져오기 완료: ${res.imported_count}건` +
          (res.skipped_count ? `, 중복 건너뜀 ${res.skipped_count}건` : "")
      );
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "카드내역 업로드 실패");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const totalAmount = items.reduce((sum, i) => sum + (i.total_amount_krw ?? 0), 0);
  const cancelledCount = items.filter((i) => i.cancelled).length;

  return (
    <main className="shell">
      <Sidebar active="statements" />

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>카드내역 관리</h1>
            <p>카드사에서 내려받은 결제내역(엑셀)을 거래로 가져오고 계정과목을 자동 분류합니다.</p>
          </div>
          <div className="toolbar">
            <select value={cardCompany} onChange={(e) => setCardCompany(e.target.value)}>
              {CARD_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <button onClick={() => fileRef.current?.click()} disabled={uploading}>
              {uploading ? "가져오는 중..." : "엑셀 업로드"}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".xls,.xlsx"
              style={{ display: "none" }}
              onChange={handleUpload}
            />
          </div>
        </header>

        {message && <p style={{ color: "var(--success)", marginTop: 16 }}>{message}</p>}
        {error && <p style={{ color: "var(--danger)", marginTop: 16 }}>{error}</p>}

        <section className="summaryGrid">
          <StatCard
            icon="receipt"
            tone="primary"
            hero
            label="전체 거래"
            value={`${items.length.toLocaleString("ko-KR")}건`}
          />
          <StatCard icon="coins" tone="info" label="총 이용금액" value={money(totalAmount)} />
          <StatCard
            icon="alert"
            tone={cancelledCount ? "warn" : "neutral"}
            label="취소 건"
            value={`${cancelledCount.toLocaleString("ko-KR")}건`}
          />
        </section>

        {loading ? (
          <div className="loader">불러오는 중...</div>
        ) : items.length === 0 ? (
          <div className="emptyState">가져온 카드내역이 없습니다.</div>
        ) : (
          <>
            <div className="tableHead">
              <span style={{ fontSize: 13, color: "var(--muted)", fontWeight: 600 }}>
                {items.length.toLocaleString("ko-KR")}건
              </span>
            </div>
            <table className="dataTable">
              <thead>
                <tr>
                  {["거래일", "가맹점", "계정과목", "할부", "이용금액", "카드사", "상태"].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} onClick={() => setSelected(item)} style={{ cursor: "pointer" }}>
                    <td>{item.transaction_date ?? "-"}</td>
                    <td>{item.merchant_name ?? "-"}</td>
                    <td>
                      <span className="badge badge-info">{item.account_code ?? "미분류"}</span>
                    </td>
                    <td>{item.installment_months ? `${item.installment_months}개월` : "일시불"}</td>
                    <td>{money(item.total_amount_krw)}</td>
                    <td>{cardLabel(item.card_company)}</td>
                    <td>
                      {item.cancelled ? (
                        <span className="badge badge-danger">취소</span>
                      ) : (
                        <span className="badge">{item.status}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>

      {selected && (
        <div className="modalBackdrop" onClick={() => setSelected(null)}>
          <div className="modalPanel" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", gap: 16, marginBottom: 20 }}>
              <div>
                <p style={{ color: "var(--muted)", fontSize: 12, margin: 0 }}>
                  {cardLabel(selected.card_company)} 결제내역
                </p>
                <h2 style={{ fontSize: 20, marginTop: 4 }}>{selected.merchant_name ?? "-"}</h2>
              </div>
              <button className="secondary" onClick={() => setSelected(null)}>
                닫기
              </button>
            </div>

            <div className="formGrid">
              <label>
                거래일
                <strong>{selected.transaction_date ?? "-"}</strong>
              </label>
              <label>
                거래시각
                <strong>{selected.transaction_time ?? "-"}</strong>
              </label>
              <label>
                이용금액
                <strong>{money(selected.total_amount_krw)}</strong>
              </label>
              <label>
                할부
                <strong>
                  {selected.installment_months ? `${selected.installment_months}개월` : "일시불"}
                </strong>
              </label>
              <label>
                계정과목
                <strong>{selected.account_code ?? "미분류"}</strong>
              </label>
              <label>
                승인번호
                <strong>{selected.approval_no ?? "-"}</strong>
              </label>
              <label>
                카드번호
                <strong>{selected.card_no_masked ?? "-"}</strong>
              </label>
              <label>
                상태
                <strong>{selected.cancelled ? "취소" : selected.status}</strong>
              </label>
              <label className="wide">
                원본 파일
                <strong>{selected.source_filename}</strong>
              </label>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

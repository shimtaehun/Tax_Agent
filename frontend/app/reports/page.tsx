"use client";

import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import {
  downloadMonthlyReportHtml,
  getMonthlyReport,
  isLoggedIn,
  MonthlyReport,
} from "../../lib/api";

const money = (value: number) => `${value.toLocaleString("ko-KR")}원`;

function currentMonth() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

export default function ReportsPage() {
  const [month, setMonth] = useState(currentMonth());
  const [report, setReport] = useState<MonthlyReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!isLoggedIn()) {
      window.location.href = "/login";
      return;
    }
    load();
  }, []);

  async function load(targetMonth = month) {
    setLoading(true);
    setError("");
    try {
      setReport(await getMonthlyReport(1, targetMonth));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "월별 리포트 조회 실패");
    } finally {
      setLoading(false);
    }
  }

  async function handleDownload() {
    try {
      await downloadMonthlyReportHtml(1, month);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "리포트 다운로드 실패");
    }
  }

  return (
    <main className="shell">
      <Sidebar active="reports" />

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>월별 마감 리포트</h1>
            <p>영수증 처리 현황, 매입세액, 매출세액, 다음 신고 기한을 월 단위로 확인합니다.</p>
          </div>
          <div className="toolbar">
            <input
              type="month"
              value={month}
              onChange={(e) => setMonth(e.target.value)}
            />
            <button onClick={() => load(month)}>조회</button>
            <button className="secondary" onClick={handleDownload} disabled={!report}>HTML 다운로드</button>
          </div>
        </header>

        {error && <p style={{ color: "#dc2626", marginTop: 16 }}>{error}</p>}
        {loading ? (
          <p style={{ marginTop: 24 }}>불러오는 중...</p>
        ) : report ? (
          <>
            <section className="summaryGrid">
              <div className="metric"><span>처리된 영수증</span><strong>{report.processed_receipt_count.toLocaleString("ko-KR")}건</strong></div>
              <div className="metric"><span>매입 세금계산서</span><strong>{report.purchase_invoice_count.toLocaleString("ko-KR")}건</strong></div>
              <div className="metric"><span>매출 세금계산서</span><strong>{report.sales_invoice_count.toLocaleString("ko-KR")}건</strong></div>
              <div className="metric"><span>매입세액 합계</span><strong>{money(report.total_input_vat_krw)}</strong></div>
              <div className="metric"><span>매출세액</span><strong>{money(report.sales_invoice_vat_krw)}</strong></div>
              <div className="metric"><span>예상 납부세액</span><strong>{money(report.estimated_vat_payable_krw)}</strong></div>
            </section>

            <section className="reportPanel">
              <h2>{report.month} 정산 요약</h2>
              <dl>
                <div><dt>기간</dt><dd>{report.from_date} - {report.to_date}</dd></div>
                <div><dt>검토 대기 영수증</dt><dd>{report.pending_receipt_count.toLocaleString("ko-KR")}건</dd></div>
                <div><dt>영수증 매입세액</dt><dd>{money(report.receipt_input_vat_krw)}</dd></div>
                <div><dt>세금계산서 매입세액</dt><dd>{money(report.purchase_invoice_vat_krw)}</dd></div>
                <div>
                  <dt>다음 신고 기한</dt>
                  <dd>
                    {report.next_deadline
                      ? `${report.next_deadline.due_date} / ${report.next_deadline.description}`
                      : "예정된 신고 기한 없음"}
                  </dd>
                </div>
              </dl>
            </section>
          </>
        ) : (
          <div className="emptyState">리포트 데이터가 없습니다.</div>
        )}
      </section>
    </main>
  );
}

"use client";

import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import StatCard from "../components/StatCard";
import { DonutChart, BarList } from "../components/Charts";
import {
  downloadMonthlyReportHtml,
  getMonthlyReport,
  isLoggedIn,
  MonthlyReport,
} from "../../lib/api";

const money = (value: number) => `${value.toLocaleString("ko-KR")}원`;
const compactWon = (value: number) =>
  value >= 10000 ? `${Math.round(value / 10000).toLocaleString("ko-KR")}만` : value.toLocaleString("ko-KR");

function defaultMonth() {
  const now = new Date();
  const prev = new Date(now.getFullYear(), now.getMonth() - 1, 1);
  return `${prev.getFullYear()}-${String(prev.getMonth() + 1).padStart(2, "0")}`;
}

export default function ReportsPage() {
  const [month, setMonth] = useState(defaultMonth());
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

        {error && <p style={{ color: "var(--danger)", marginTop: 16 }}>{error}</p>}
        {loading ? (
          <div className="loader">불러오는 중...</div>
        ) : report ? (
          <>
            <section className="summaryGrid">
              <StatCard icon="receipt" tone="neutral" label="처리된 영수증" value={`${report.processed_receipt_count.toLocaleString("ko-KR")}건`} />
              <StatCard icon="fileIn" tone="info" label="매입 세금계산서" value={`${report.purchase_invoice_count.toLocaleString("ko-KR")}건`} />
              <StatCard icon="fileOut" tone="success" label="매출 세금계산서" value={`${report.sales_invoice_count.toLocaleString("ko-KR")}건`} />
              <StatCard icon="coins" tone="info" label="매입세액 합계" value={money(report.total_input_vat_krw)} />
              <StatCard icon="trending" tone="success" label="매출세액" value={money(report.sales_invoice_vat_krw)} />
              <StatCard icon="scale" tone="primary" hero label="예상 납부세액" value={money(report.estimated_vat_payable_krw)} />
            </section>

            <div className="section-head">정산 시각화</div>
            <section className="chartGrid">
              <div className="chartCard rise">
                <h3>매입세액 구성</h3>
                <DonutChart
                  centerLabel="매입세액"
                  centerValue={compactWon(report.total_input_vat_krw)}
                  format={money}
                  segments={[
                    { label: "영수증 매입세액", value: report.receipt_input_vat_krw, color: "#4f46e5" },
                    { label: "세금계산서 매입세액", value: report.purchase_invoice_vat_krw, color: "#38bdf8" },
                  ]}
                />
              </div>
              <div className="chartCard rise">
                <h3>매출세액 · 매입세액 · 예상 납부세액</h3>
                <BarList
                  format={money}
                  items={[
                    { label: "매출세액", value: report.sales_invoice_vat_krw, color: "#059669" },
                    { label: "매입세액(공제)", value: report.total_input_vat_krw, color: "#2563eb" },
                    { label: "예상 납부세액", value: report.estimated_vat_payable_krw, color: "#4f46e5" },
                  ]}
                />
              </div>
            </section>

            <section className="darkCard rise">
              <div className="darkHead">
                <span className="brand-mark" aria-hidden>
                  <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 3v3M12 18v3M5.6 5.6l2.1 2.1M16.3 16.3l2.1 2.1M3 12h3M18 12h3" />
                    <circle cx="12" cy="12" r="3.2" />
                  </svg>
                </span>
                <h3>AI 리포트 요약</h3>
              </div>
              <ul>
                <li>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#34d399" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M20 6 9 17l-5-5" /></svg>
                  <span>{report.month} 예상 납부세액은 <strong>{money(report.estimated_vat_payable_krw)}</strong>입니다. 매출세액 {money(report.sales_invoice_vat_krw)}에서 매입세액 {money(report.total_input_vat_krw)}을 공제한 값입니다.</span>
                </li>
                <li>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#fbbf24" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M10.3 3.7 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.7a2 2 0 0 0-3.4 0Z" /><path d="M12 9v4M12 17h.01" /></svg>
                  <span>검토 대기 영수증이 <strong>{report.pending_receipt_count.toLocaleString("ko-KR")}건</strong> 남아 있습니다. 신고 전에 처리하면 매입세액 공제가 정확해집니다.</span>
                </li>
                <li>
                  <svg viewBox="0 0 24 24" fill="none" stroke="#818cf8" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" /><path d="M16 2v4M8 2v4M3 10h18" /></svg>
                  <span>{report.next_deadline ? <>다음 신고 기한은 <strong>{report.next_deadline.due_date}</strong> ({report.next_deadline.description})입니다.</> : "예정된 신고 기한이 없습니다."}</span>
                </li>
              </ul>
            </section>

            <section className="reportPanel rise">
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

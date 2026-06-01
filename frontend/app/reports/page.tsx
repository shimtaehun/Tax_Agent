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

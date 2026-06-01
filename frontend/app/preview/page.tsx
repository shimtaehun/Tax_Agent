"use client";

// 임시 시각 확인용 프리뷰 (백엔드/인증 불필요). 확인 후 삭제 예정.
import Sidebar from "../components/Sidebar";
import StatCard from "../components/StatCard";
import { DonutChart, BarList } from "../components/Charts";

const won = (v: number) => `${v.toLocaleString("ko-KR")}원`;

// 샘플 영수증 이미지 (data URI) — 프리뷰 전용
const SAMPLE_RECEIPT =
  "data:image/svg+xml;utf8," +
  encodeURIComponent(`
<svg xmlns='http://www.w3.org/2000/svg' width='320' height='440' viewBox='0 0 320 440'>
  <rect width='320' height='440' fill='#ffffff'/>
  <text x='160' y='48' text-anchor='middle' font-family='monospace' font-size='22' font-weight='700' fill='#111'>STARBUCKS</text>
  <text x='160' y='72' text-anchor='middle' font-family='monospace' font-size='12' fill='#666'>강남대로점 02-555-1234</text>
  <line x1='28' y1='96' x2='292' y2='96' stroke='#ddd' stroke-dasharray='4 4'/>
  <text x='28' y='128' font-family='monospace' font-size='13' fill='#222'>아메리카노 (T)</text>
  <text x='292' y='128' text-anchor='end' font-family='monospace' font-size='13' fill='#222'>4,500</text>
  <text x='28' y='154' font-family='monospace' font-size='13' fill='#222'>카페라떼 (T)</text>
  <text x='292' y='154' text-anchor='end' font-family='monospace' font-size='13' fill='#222'>5,000</text>
  <text x='28' y='180' font-family='monospace' font-size='13' fill='#222'>치즈케이크</text>
  <text x='292' y='180' text-anchor='end' font-family='monospace' font-size='13' fill='#222'>6,500</text>
  <line x1='28' y1='200' x2='292' y2='200' stroke='#ddd' stroke-dasharray='4 4'/>
  <text x='28' y='230' font-family='monospace' font-size='14' font-weight='700' fill='#111'>합계</text>
  <text x='292' y='230' text-anchor='end' font-family='monospace' font-size='14' font-weight='700' fill='#111'>16,000</text>
  <text x='28' y='256' font-family='monospace' font-size='12' fill='#666'>부가세</text>
  <text x='292' y='256' text-anchor='end' font-family='monospace' font-size='12' fill='#666'>1,454</text>
  <line x1='28' y1='280' x2='292' y2='280' stroke='#ddd' stroke-dasharray='4 4'/>
  <text x='28' y='308' font-family='monospace' font-size='12' fill='#444'>신용카드 승인</text>
  <text x='28' y='330' font-family='monospace' font-size='12' fill='#444'>****-****-1234</text>
  <text x='160' y='380' text-anchor='middle' font-family='monospace' font-size='12' fill='#888'>2026-05-31 14:21</text>
  <text x='160' y='404' text-anchor='middle' font-family='monospace' font-size='11' fill='#aaa'>이용해 주셔서 감사합니다</text>
</svg>`);

const WORKFLOW_STAGES = ["업로드", "영수증 인식", "법령 검색", "세무사 검토", "결과 저장"];

export default function Preview() {
  const activeStage = 3;
  return (
    <main className="shell">
      <Sidebar active="reviews">
        <div className="reviewList">
          <div className="navSectionLabel">검토 대기<span className="count">3</span></div>
          <button className="listItem listItemActive"><span>#142</span><span className="listName">스타벅스_영수증.jpg</span></button>
          <button className="listItem"><span>#141</span><span className="listName">택시영수증_0531.png</span></button>
          <button className="listItem"><span>#140</span><span className="listName">사무용품_구매.pdf</span></button>
        </div>
      </Sidebar>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>영수증 검토</h1>
            <p>AI가 증빙과 계산 후보를 정리하고, 최종 판단은 세무사가 승인합니다.</p>
          </div>
          <button>영수증 업로드</button>
        </header>

        <section className="statStrip">
          <StatCard icon="receipt" tone="primary" hero label="검토 대기" value="3건" />
          <StatCard icon="clock" tone="info" label="AI 처리 중" value="1건" />
          <StatCard icon="alert" tone="danger" label="처리 실패" value="0건" />
        </section>

        <div className="section-head">처리 단계</div>
        <section className="statusGrid">
          {WORKFLOW_STAGES.map((stage, i) => {
            const status = i < activeStage ? "complete" : i === activeStage ? "active" : "pending";
            const label = status === "complete" ? "완료" : status === "active" ? "진행 중" : "대기";
            return (
              <div className={`stage ${status}`} key={stage}>
                <div className="step">
                  {status === "complete" ? (
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"><path d="m5 12 5 5L20 6" /></svg>
                  ) : (i + 1)}
                </div>
                <div className="txt"><span>{stage}</span><strong>{label}</strong></div>
              </div>
            );
          })}
        </section>

        <section className="reviewPanel">
          <div className="receiptPreview">
            <div className="previewHead">
              <div style={{ minWidth: 0 }}>
                <span className="previewKicker">영수증 #142</span>
                <strong className="previewName">스타벅스_영수증.jpg</strong>
              </div>
              <span className="badge badge-warn">검토 필요</span>
            </div>
            <div className="paper">
              <img className="previewImg" alt="영수증 샘플" src={SAMPLE_RECEIPT} />
            </div>
            <small className="previewFoot">업로드: 2026년 5월 31일 14:22</small>
          </div>

          <div className="decision">
            <h2>세무사 검토</h2>
            <dl>
              <div><dt>영수증 ID</dt><dd>#142</dd></div>
              <div><dt>파일명</dt><dd>스타벅스_영수증.jpg</dd></div>
              <div><dt>상태</dt><dd>검토 필요</dd></div>
            </dl>

            <div className="detailBox">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                <h3>AI 판단 초안</h3>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)" }}>신뢰도</span>
                  <div className="ring" data-label="86" style={{ ["--val" as string]: 86, ["--ring-color" as string]: "var(--success)" }} />
                </div>
              </div>
              <div className="kv">
                <span>계정과목</span><strong>복리후생비</strong>
                <span>증빙</span><strong>신용카드매출전표</strong>
                <span>부가세 공제</span><strong>가능</strong>
              </div>
              <div className="flags"><span>금액 불일치 의심</span><span>접대비 한도 확인</span></div>
            </div>

            <div className="detailBox">
              <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
                법령 검색 결과
                <span className="badge badge-success">2개 인용</span>
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div style={{ padding: "12px 14px", background: "var(--panel)", border: "1px solid var(--line)", borderLeft: "3px solid var(--info)", borderRadius: 10, fontSize: 13 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                    <strong style={{ color: "var(--info)" }}>부가가치세법 제38조 ①</strong>
                    <span style={{ fontSize: 11, color: "var(--muted)" }}>2024-01-01 시행</span>
                  </div>
                  <p style={{ margin: 0, color: "#374151", lineHeight: 1.6 }}>사업자가 자기의 사업을 위하여 사용하였거나 사용할 목적으로 공급받은 재화 또는 용역에 대한 매입세액은 매출세액에서 공제한다.</p>
                </div>
              </div>
            </div>

            <div className="detailBox">
              <h3>코멘트</h3>
              <div className="commentList">
                <div className="commentItem"><span>#담당자</span><p>거래처 확인 필요합니다.</p></div>
              </div>
              <div className="commentForm">
                <input placeholder="코멘트 입력" />
                <button type="button">등록</button>
              </div>
            </div>

            <button type="button" className="secondary">감사 로그 CSV</button>

            <div className="actions" style={{ marginTop: 16 }}>
              <button className="btn-ghost-danger">반려</button>
              <button className="btn-success">승인</button>
            </div>
          </div>
        </section>

        <div className="section-head">월별 지표 (reports 미리보기)</div>
        <section className="summaryGrid">
          <StatCard icon="receipt" tone="neutral" label="처리된 영수증" value="128건" />
          <StatCard icon="fileIn" tone="info" label="매입세액 합계" value="1,240,000원" />
          <StatCard icon="trending" tone="success" label="매출세액" value="2,180,000원" />
          <StatCard icon="scale" tone="primary" hero label="예상 납부세액" value="940,000원" />
        </section>

        <div className="section-head">정산 시각화</div>
        <section className="chartGrid">
          <div className="chartCard">
            <h3>매입세액 구성</h3>
            <DonutChart centerLabel="매입세액" centerValue="124만" format={won}
              segments={[
                { label: "영수증 매입세액", value: 420000, color: "#4f46e5" },
                { label: "세금계산서 매입세액", value: 820000, color: "#38bdf8" },
              ]} />
          </div>
          <div className="chartCard">
            <h3>매출세액 · 매입세액 · 예상 납부세액</h3>
            <BarList format={won}
              items={[
                { label: "매출세액", value: 2180000, color: "#059669" },
                { label: "매입세액(공제)", value: 1240000, color: "#2563eb" },
                { label: "예상 납부세액", value: 940000, color: "#4f46e5" },
              ]} />
          </div>
        </section>

        <table className="dataTable text-left" style={{ marginTop: 20 }}>
          <thead><tr>{["ID", "파일명", "상태", "계정과목", "처리일시"].map((h) => <th key={h}>{h}</th>)}</tr></thead>
          <tbody>
            <tr><td style={{ color: "var(--muted)" }}>#139</td><td style={{ fontWeight: 600 }}>회식비_영수증.jpg</td><td><span className="badge badge-success">승인</span></td><td>복리후생비</td><td>2026-05-30 18:10</td></tr>
            <tr><td style={{ color: "var(--muted)" }}>#138</td><td style={{ fontWeight: 600 }}>주유소_5월.png</td><td><span className="badge badge-danger">반려</span></td><td>—</td><td>2026-05-29 09:44</td></tr>
          </tbody>
        </table>
      </section>
    </main>
  );
}

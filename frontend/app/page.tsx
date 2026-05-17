const stages = [
  { label: "업로드", status: "complete", statusLabel: "완료" },
  { label: "영수증 인식", status: "complete", statusLabel: "완료" },
  { label: "법령 검색", status: "complete", statusLabel: "완료" },
  { label: "세무사 검토", status: "active", statusLabel: "검토 중" },
  { label: "결과 저장", status: "pending", statusLabel: "대기" },
];

export default function Home() {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">Tax-Copilot</div>
        <nav>
          <a className="active">영수증 검토</a>
          <a>검토 대기함</a>
          <a>감사 로그</a>
        </nav>
      </aside>
      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>영수증 검토</h1>
            <p>AI가 증빙과 계산 후보를 정리하고, 최종 판단은 세무사가 승인합니다.</p>
          </div>
          <button>영수증 업로드</button>
        </header>

        <section className="statusGrid">
          {stages.map((stage) => (
            <div className={`stage ${stage.status}`} key={stage.label}>
              <span>{stage.label}</span>
              <strong>{stage.statusLabel}</strong>
            </div>
          ))}
        </section>

        <section className="reviewPanel">
          <div className="receiptPreview">
            <div className="paper">
              <span>모의 가맹점</span>
              <strong>11,000원</strong>
              <small>2026-01-15 · 신용카드 매출전표</small>
            </div>
          </div>
          <div className="decision">
            <h2>판단 후보</h2>
            <dl>
              <div>
                <dt>증빙</dt>
                <dd>신용카드 매출전표 · 유효</dd>
              </div>
              <div>
                <dt>부가세</dt>
                <dd>공급가액 10,000원 / 부가세 1,000원</dd>
              </div>
              <div>
                <dt>검토 사유</dt>
                <dd>사업 관련성 확인 필요</dd>
              </div>
              <div>
                <dt>법령 근거</dt>
                <dd>부가가치세법 제39조</dd>
              </div>
            </dl>
            <div className="actions">
              <button className="secondary">반려</button>
              <button>승인</button>
            </div>
          </div>
        </section>
      </section>
    </main>
  );
}

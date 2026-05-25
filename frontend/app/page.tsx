"use client";

import { useEffect, useState, useRef, ChangeEvent } from "react";
import {
  isLoggedIn,
  logout,
  getPendingReviews,
  uploadReceipt,
  decide,
  ReviewItem,
} from "../lib/api";

const STATUS_LABEL: Record<string, string> = {
  PENDING: "대기",
  PROCESSING: "처리 중",
  NEEDS_REVIEW: "검토 필요",
  APPROVED: "승인",
  REJECTED: "반려",
  FAILED: "실패",
};

const WORKFLOW_STAGES = [
  "업로드",
  "영수증 인식",
  "법령 검색",
  "세무사 검토",
  "결과 저장",
];

export default function Home() {
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [selected, setSelected] = useState<ReviewItem | null>(null);
  const [comment, setComment] = useState("");
  const [deciding, setDeciding] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [loading, setLoading] = useState(true);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!isLoggedIn()) {
      window.location.href = "/login";
      return;
    }
    fetchReviews();
  }, []);

  async function fetchReviews() {
    setLoading(true);
    const data = await getPendingReviews();
    setReviews(data);
    if (data.length > 0 && !selected) setSelected(data[0]);
    setLoading(false);
  }

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg("");
    try {
      const res = await uploadReceipt(file);
      setUploadMsg(`영수증 #${res.receipt_id} 업로드 완료. AI 처리가 시작되었습니다.`);
      setTimeout(fetchReviews, 3000);
    } catch (err: unknown) {
      setUploadMsg(err instanceof Error ? err.message : "업로드 실패");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handleDecide(approved: boolean) {
    if (!selected) return;
    setDeciding(true);
    try {
      await decide(selected.receipt_id, approved, comment);
      setComment("");
      setSelected(null);
      await fetchReviews();
    } catch {
      // 에러는 무시하고 목록만 갱신
      await fetchReviews();
    } finally {
      setDeciding(false);
    }
  }

  const activeStage = selected ? 3 : 0; // 검토 단계가 현재 활성

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">Tax-Copilot</div>
        <nav>
          <a className="active">영수증 검토</a>
          <a onClick={logout} style={{ cursor: "pointer" }}>
            로그아웃
          </a>
        </nav>
        {reviews.length > 0 && (
          <div className="reviewList">
            <p style={{ fontSize: 12, color: "#94a3b8", margin: "24px 0 8px" }}>
              검토 대기 ({reviews.length})
            </p>
            {reviews.map((r) => (
              <button
                key={r.receipt_id}
                className={`listItem ${selected?.receipt_id === r.receipt_id ? "listItemActive" : ""}`}
                onClick={() => setSelected(r)}
              >
                <span>#{r.receipt_id}</span>
                <span className="listName">{r.original_filename}</span>
              </button>
            ))}
          </div>
        )}
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>영수증 검토</h1>
            <p>AI가 증빙과 계산 후보를 정리하고, 최종 판단은 세무사가 승인합니다.</p>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
            <button onClick={() => fileRef.current?.click()} disabled={uploading}>
              {uploading ? "업로드 중..." : "영수증 업로드"}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".jpg,.jpeg,.png,.pdf"
              style={{ display: "none" }}
              onChange={handleUpload}
            />
            {uploadMsg && <small style={{ color: "var(--muted)", maxWidth: 260, textAlign: "right" }}>{uploadMsg}</small>}
          </div>
        </header>

        <section className="statusGrid">
          {WORKFLOW_STAGES.map((stage, i) => {
            const status =
              i < activeStage ? "complete" : i === activeStage ? "active" : "pending";
            const label =
              status === "complete" ? "완료" : status === "active" ? "진행 중" : "대기";
            return (
              <div className={`stage ${status}`} key={stage}>
                <span>{stage}</span>
                <strong>{label}</strong>
              </div>
            );
          })}
        </section>

        {loading ? (
          <p style={{ color: "var(--muted)" }}>불러오는 중...</p>
        ) : selected ? (
          <section className="reviewPanel">
            <div className="receiptPreview">
              <div className="paper">
                <span style={{ color: "var(--muted)", fontSize: 13 }}>영수증 #{selected.receipt_id}</span>
                <strong style={{ fontSize: 18 }}>{selected.original_filename}</strong>
                <small>
                  업로드:{" "}
                  {new Date(selected.created_at).toLocaleDateString("ko-KR", {
                    year: "numeric",
                    month: "long",
                    day: "numeric",
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </small>
                <div
                  style={{
                    marginTop: 16,
                    padding: "12px 16px",
                    background: "#fef3c7",
                    borderRadius: 6,
                    fontSize: 13,
                    color: "#92400e",
                  }}
                >
                  AI가 처리를 완료했습니다. 세무사 검토가 필요합니다.
                </div>
              </div>
            </div>

            <div className="decision">
              <h2>세무사 검토</h2>
              <dl>
                <div>
                  <dt>영수증 ID</dt>
                  <dd>#{selected.receipt_id}</dd>
                </div>
                <div>
                  <dt>파일명</dt>
                  <dd>{selected.original_filename}</dd>
                </div>
                <div>
                  <dt>상태</dt>
                  <dd>{STATUS_LABEL["NEEDS_REVIEW"]}</dd>
                </div>
                <div>
                  <dt>워크플로우 ID</dt>
                  <dd style={{ fontSize: 12, wordBreak: "break-all", color: "var(--muted)" }}>
                    {selected.langgraph_thread_id}
                  </dd>
                </div>
              </dl>

              <div style={{ marginBottom: 16 }}>
                <label
                  style={{
                    display: "block",
                    color: "var(--muted)",
                    fontWeight: 700,
                    fontSize: 14,
                    marginBottom: 6,
                  }}
                >
                  검토 의견 (선택)
                </label>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="승인 또는 반려 사유를 입력하세요..."
                  style={{
                    width: "100%",
                    padding: "10px 12px",
                    border: "1px solid var(--line)",
                    borderRadius: 6,
                    fontSize: 14,
                    resize: "vertical",
                    minHeight: 80,
                    fontFamily: "inherit",
                  }}
                />
              </div>

              <div className="actions">
                <button
                  className="secondary"
                  onClick={() => handleDecide(false)}
                  disabled={deciding}
                >
                  반려
                </button>
                <button onClick={() => handleDecide(true)} disabled={deciding}>
                  {deciding ? "처리 중..." : "승인"}
                </button>
              </div>
            </div>
          </section>
        ) : (
          <div
            style={{
              background: "var(--panel)",
              border: "1px solid var(--line)",
              borderRadius: 8,
              padding: "48px 28px",
              textAlign: "center",
              color: "var(--muted)",
            }}
          >
            {reviews.length === 0
              ? "검토 대기 중인 영수증이 없습니다. 영수증을 업로드하세요."
              : "왼쪽 목록에서 영수증을 선택하세요."}
          </div>
        )}
      </section>
    </main>
  );
}

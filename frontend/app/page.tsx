"use client";

import { useEffect, useState, useRef, ChangeEvent } from "react";
import Sidebar from "./components/Sidebar";
import StatCard from "./components/StatCard";
import {
  isLoggedIn,
  getPendingReviews,
  uploadReceipt,
  decide,
  getReceiptExplanation,
  getReceiptComments,
  createReceiptComment,
  downloadAuditCsv,
  getReceipts,
  retryReceipt,
  cancelReceipt,
  fetchReceiptFile,
  ReviewItem,
  ExplanationResponse,
  CitationItem,
  CommentItem,
  ReceiptStatus,
  ReceiptFile,
} from "../lib/api";

const STATUS_LABEL: Record<string, string> = {
  PENDING: "대기",
  PROCESSING: "처리 중",
  NEEDS_REVIEW: "검토 필요",
  APPROVED: "승인",
  REJECTED: "반려",
  FAILED: "실패",
};

const STATUS_COLOR: Record<string, string> = {
  PENDING: "var(--faint)",
  PROCESSING: "var(--info)",
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
  const [failedReceipts, setFailedReceipts] = useState<ReceiptStatus[]>([]);
  const [processingReceipts, setProcessingReceipts] = useState<ReceiptStatus[]>([]);
  const [selected, setSelected] = useState<ReviewItem | null>(null);
  const [comment, setComment] = useState("");
  const [deciding, setDeciding] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadMsg, setUploadMsg] = useState("");
  const [loading, setLoading] = useState(true);
  const [detail, setDetail] = useState<ExplanationResponse | null>(null);
  const [comments, setComments] = useState<CommentItem[]>([]);
  const [newComment, setNewComment] = useState("");
  const [detailError, setDetailError] = useState("");
  const [filePreview, setFilePreview] = useState<ReceiptFile | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);
  const pollingTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const selectedRef = useRef<ReviewItem | null>(null);

  useEffect(() => { selectedRef.current = selected; }, [selected]);

  useEffect(() => {
    if (!isLoggedIn()) { window.location.href = "/login"; return; }
    fetchReviews();
    return () => {
      if (pollingTimerRef.current) clearTimeout(pollingTimerRef.current);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!selected) { setDetail(null); setComments([]); setFilePreview(null); return; }
    loadDetail(selected.receipt_id);

    let objUrl: string | null = null;
    setFilePreview(null);
    setPreviewLoading(true);
    fetchReceiptFile(selected.receipt_id)
      .then((f) => { objUrl = f.url; setFilePreview(f); })
      .catch(() => setFilePreview(null))
      .finally(() => setPreviewLoading(false));
    return () => { if (objUrl) URL.revokeObjectURL(objUrl); };
  }, [selected]);

  async function fetchReviews() {
    if (pollingTimerRef.current) {
      clearTimeout(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }

    setLoading(true);
    try {
      const [reviewsData, failedData, pendingData, processingData] = await Promise.all([
        getPendingReviews(),
        getReceipts("FAILED"),
        getReceipts("PENDING"),
        getReceipts("PROCESSING"),
      ]);
      setReviews(reviewsData);
      setFailedReceipts(failedData.items);
      const inProgress = [...pendingData.items, ...processingData.items];
      setProcessingReceipts(inProgress);

      if (reviewsData.length > 0 && !selectedRef.current) {
        setSelected(reviewsData[0]);
      }

      // 처리 중인 영수증이 있으면 5초 후 자동 새로고침
      if (inProgress.length > 0) {
        pollingTimerRef.current = setTimeout(fetchReviews, 5000);
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setUploadMsg("");
    try {
      const res = await uploadReceipt(file);
      setUploadMsg(`영수증 #${res.receipt_id} 업로드 완료. AI 처리 중...`);
      await fetchReviews();
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
      await fetchReviews();
    } finally {
      setDeciding(false);
    }
  }

  async function loadDetail(receiptId: number) {
    setDetailError("");
    try {
      const [explanation, commentItems] = await Promise.all([
        getReceiptExplanation(receiptId),
        getReceiptComments(receiptId),
      ]);
      setDetail(explanation);
      setComments(commentItems);
    } catch (err: unknown) {
      setDetailError(err instanceof Error ? err.message : "상세 조회 실패");
    }
  }

  async function handleCommentSubmit() {
    if (!selected || !newComment.trim()) return;
    try {
      const saved = await createReceiptComment(selected.receipt_id, newComment.trim());
      setComments((prev) => [...prev, saved]);
      setNewComment("");
    } catch (err: unknown) {
      setDetailError(err instanceof Error ? err.message : "코멘트 등록 실패");
    }
  }

  async function handleRetry(receiptId: number) {
    try {
      await retryReceipt(receiptId);
      await fetchReviews();
    } catch (err: unknown) {
      setUploadMsg(err instanceof Error ? err.message : "재처리 요청 실패");
    }
  }

  async function handleCancel(receiptId: number) {
    try {
      await cancelReceipt(receiptId);
      await fetchReviews();
    } catch (err: unknown) {
      setUploadMsg(err instanceof Error ? err.message : "취소 실패");
    }
  }

  const activeStage = selected ? 3 : 0;

  return (
    <main className="shell">
      <Sidebar active="reviews">
        {processingReceipts.length > 0 && (
          <div className="reviewList">
            <div className="navSectionLabel">
              <span style={{ display: "inline-block", width: 8, height: 8, borderRadius: "50%", background: "var(--info)", animation: "pulse 1.5s infinite" }} />
              AI 처리 중
              <span className="count">{processingReceipts.length}</span>
            </div>
            {processingReceipts.map((r) => (
              <div
                key={r.receipt_id}
                className="listItem"
                style={{ cursor: "default", display: "flex", alignItems: "center", justifyContent: "space-between" }}
              >
                <div style={{ display: "flex", flexDirection: "column", overflow: "hidden" }}>
                  <span style={{ color: STATUS_COLOR[r.status] ?? "var(--info)", fontSize: 11, fontWeight: 700 }}>
                    {STATUS_LABEL[r.status]}
                  </span>
                  <span className="listName">#{r.receipt_id} {r.original_filename}</span>
                </div>
                <button
                  onClick={() => handleCancel(r.receipt_id)}
                  title="처리 취소"
                  style={{
                    flexShrink: 0,
                    marginLeft: 6,
                    width: 22,
                    height: 22,
                    borderRadius: "50%",
                    border: "none",
                    background: "var(--danger-soft)",
                    color: "var(--danger)",
                    fontSize: 14,
                    fontWeight: 700,
                    cursor: "pointer",
                    lineHeight: 1,
                    padding: 0,
                    boxShadow: "none",
                  }}
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}

        {reviews.length > 0 && (
          <div className="reviewList">
            <div className="navSectionLabel">
              검토 대기
              <span className="count">{reviews.length}</span>
            </div>
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

        {failedReceipts.length > 0 && (
          <div className="reviewList">
            <div className="navSectionLabel" style={{ color: "var(--danger)" }}>
              처리 실패
              <span className="count">{failedReceipts.length}</span>
            </div>
            {failedReceipts.map((r) => (
              <button
                key={r.receipt_id}
                className="listItem"
                onClick={() => handleRetry(r.receipt_id)}
                title="재처리 요청"
              >
                <span>#{r.receipt_id} 재처리</span>
                <span className="listName">{r.original_filename}</span>
              </button>
            ))}
          </div>
        )}
      </Sidebar>

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
            {uploadMsg && (
              <small style={{ color: "var(--muted)", maxWidth: 260, textAlign: "right" }}>
                {uploadMsg}
              </small>
            )}
          </div>
        </header>

        <section className="statStrip">
          <StatCard icon="receipt" tone="primary" hero label="검토 대기" value={`${reviews.length}건`} />
          <StatCard icon="clock" tone="info" label="AI 처리 중" value={`${processingReceipts.length}건`} />
          <StatCard icon="alert" tone="danger" label="처리 실패" value={`${failedReceipts.length}건`} />
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
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                      <path d="m5 12 5 5L20 6" />
                    </svg>
                  ) : (
                    i + 1
                  )}
                </div>
                <div className="txt">
                  <span>{stage}</span>
                  <strong>{label}</strong>
                </div>
              </div>
            );
          })}
        </section>

        {loading ? (
          <div className="loader">불러오는 중...</div>
        ) : selected ? (
          <section className="reviewPanel rise">
            <div className="receiptPreview">
              <div className="previewHead">
                <div style={{ minWidth: 0 }}>
                  <span className="previewKicker">영수증 #{selected.receipt_id}</span>
                  <strong className="previewName">{selected.original_filename}</strong>
                </div>
                <span className="badge badge-warn">검토 필요</span>
              </div>

              <div className="paper">
                {filePreview ? (
                  filePreview.contentType.includes("pdf") ? (
                    <embed className="previewDoc" src={filePreview.url} type="application/pdf" />
                  ) : (
                    <img className="previewImg" src={filePreview.url} alt={`영수증 ${selected.receipt_id}`} />
                  )
                ) : previewLoading ? (
                  <div className="previewEmpty">
                    <div className="loader">영수증 불러오는 중…</div>
                  </div>
                ) : (
                  <div className="previewEmpty">
                    <div className="empty-ic" aria-hidden>
                      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                        <path d="M14 2v6h6" />
                      </svg>
                    </div>
                    미리보기를 표시할 수 없습니다.
                  </div>
                )}
              </div>

              <small className="previewFoot">
                업로드:{" "}
                {new Date(selected.created_at).toLocaleDateString("ko-KR", {
                  year: "numeric", month: "long", day: "numeric",
                  hour: "2-digit", minute: "2-digit",
                })}
              </small>
            </div>

            <div className="decision">
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 18 }}>
                <h2>세무사 검토</h2>
                <span className="badge badge-warn">{STATUS_LABEL["NEEDS_REVIEW"]}</span>
              </div>

              {detailError && <p style={{ color: "var(--danger)", fontSize: 13 }}>{detailError}</p>}

              {detail?.decision && (
                <div className="detailBox">
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12 }}>
                    <h3>AI 판단 초안</h3>
                    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ fontSize: 11, fontWeight: 700, color: "var(--muted)" }}>신뢰도</span>
                      <div
                        className="ring"
                        data-label={`${Math.round(detail.decision.confidence * 100)}`}
                        style={{
                          ["--val" as string]: Math.round(detail.decision.confidence * 100),
                          ["--ring-color" as string]:
                            detail.decision.confidence >= 0.8 ? "var(--success)" : detail.decision.confidence >= 0.5 ? "var(--primary)" : "var(--warn)",
                        }}
                      />
                    </div>
                  </div>
                  <div className="kv">
                    <span>계정과목</span>
                    <strong>{detail.decision.account_code ?? "미분류"}</strong>
                    <span>증빙</span>
                    <strong>{detail.decision.evidence_type}</strong>
                    <span>신뢰도</span>
                    <strong>{Math.round(detail.decision.confidence * 100)}%</strong>
                    <span>부가세 공제</span>
                    <strong>
                      {detail.decision.vat_creditable === null
                        ? "검토 필요"
                        : detail.decision.vat_creditable ? "가능" : "불가"}
                    </strong>
                  </div>
                  {detail.risk_flags.length > 0 && (
                    <div className="flags">
                      {detail.risk_flags.map((flag) => (
                        <span key={flag}>{flag}</span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              <div className="detailBox">
                <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  법령 검색 결과
                  {detail && (
                    <span className={`badge ${detail.citations.length > 0 ? "badge-success" : "badge-muted"}`}>
                      {detail.citations.length > 0 ? `${detail.citations.length}개 인용` : "검색 안 됨"}
                    </span>
                  )}
                </h3>
                {!detail ? (
                  <small style={{ color: "var(--muted)" }}>불러오는 중...</small>
                ) : detail.citations.length === 0 ? (
                  <small style={{ color: "var(--muted)" }}>
                    법령 검색이 수행되지 않았습니다. (Qdrant 미연결 또는 관련 조항 없음)
                  </small>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                    {detail.citations.map((c: CitationItem) => (
                      <div key={c.chunk_id} style={{
                        padding: "12px 14px",
                        background: "var(--panel)",
                        border: "1px solid var(--line)",
                        borderLeft: "3px solid var(--info)",
                        borderRadius: 10,
                        fontSize: 13,
                      }}>
                        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
                          <strong style={{ color: "var(--info)" }}>
                            {c.law_name} {c.article_no ?? ""} {c.paragraph_no ?? ""}
                          </strong>
                          <span style={{ fontSize: 11, color: "var(--muted)" }}>
                            {c.effective_from} 시행
                          </span>
                        </div>
                        <p style={{ margin: 0, color: "var(--ink-soft)", lineHeight: 1.6 }}>
                          {c.quoted_text}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="detailBox">
                <h3>코멘트</h3>
                <div className="commentList">
                  {comments.length === 0 ? (
                    <small>등록된 코멘트가 없습니다.</small>
                  ) : (
                    comments.map((c) => (
                      <div key={c.id} className="commentItem">
                        <span>#{c.author_id}</span>
                        <p>{c.body}</p>
                      </div>
                    ))
                  )}
                </div>
                <div className="commentForm">
                  <input
                    value={newComment}
                    onChange={(e) => setNewComment(e.target.value)}
                    placeholder="코멘트 입력"
                  />
                  <button type="button" onClick={handleCommentSubmit}>등록</button>
                </div>
              </div>

              <button
                type="button"
                className="secondary"
                onClick={() => selected && downloadAuditCsv(selected.receipt_id)}
              >
                감사 로그 CSV
              </button>

              <div style={{ marginBottom: 16 }}>
                <label style={{ display: "block", color: "var(--muted)", fontWeight: 700, fontSize: 14, marginBottom: 6 }}>
                  검토 의견 (선택)
                </label>
                <textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="승인 또는 반려 사유를 입력하세요..."
                  style={{
                    width: "100%", padding: "10px 12px",
                    border: "1px solid var(--line)", borderRadius: 6,
                    fontSize: 14, resize: "vertical", minHeight: 80, fontFamily: "inherit",
                  }}
                />
              </div>

              <div className="actions">
                <button className="btn-ghost-danger" onClick={() => handleDecide(false)} disabled={deciding}>반려</button>
                <button className="btn-success" onClick={() => handleDecide(true)} disabled={deciding}>
                  {deciding ? "처리 중..." : "승인"}
                </button>
              </div>
            </div>
          </section>
        ) : (
          <div className="emptyState rise">
            <div className="empty-ic" aria-hidden>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 12h-6l-2 3h-4l-2-3H2" />
                <path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1Z" />
              </svg>
            </div>
            {processingReceipts.length > 0
              ? `영수증 ${processingReceipts.length}건을 AI가 처리 중입니다. 완료되면 자동으로 표시됩니다.`
              : reviews.length === 0
                ? "검토 대기 중인 영수증이 없습니다. 영수증을 업로드하세요."
                : "왼쪽 목록에서 영수증을 선택하세요."}
          </div>
        )}
      </section>
    </main>
  );
}

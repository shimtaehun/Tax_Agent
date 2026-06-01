"use client";

import { useEffect, useState } from "react";
import Sidebar from "../components/Sidebar";
import {
  isLoggedIn,
  getReviewHistory,
  updateReceiptReview,
  deleteReceipt,
  downloadAuditCsv,
  ReviewHistoryItem,
} from "../../lib/api";

const STATUS_LABEL: Record<string, string> = { APPROVED: "승인", REJECTED: "반려" };
const STATUS_BADGE: Record<string, string> = { APPROVED: "badge-success", REJECTED: "badge-danger" };
const STATUS_COLOR: Record<string, string> = { APPROVED: "var(--success)", REJECTED: "var(--danger)" };

export default function HistoryPage() {
  const [items, setItems] = useState<ReviewHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  // 모달 상태
  const [selected, setSelected] = useState<ReviewHistoryItem | null>(null);
  const [isEditing, setIsEditing] = useState(false);
  const [editAccountCode, setEditAccountCode] = useState("");
  const [editComment, setEditComment] = useState("");
  const [saving, setSaving] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState("");

  useEffect(() => {
    if (!isLoggedIn()) { window.location.href = "/login"; return; }
    load();
  }, []);

  async function load() {
    setLoading(true);
    try {
      setItems(await getReviewHistory());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "조회 실패");
    } finally {
      setLoading(false);
    }
  }

  function openModal(item: ReviewHistoryItem) {
    setSelected(item);
    setIsEditing(false);
    setDeleteConfirm(false);
    setActionError("");
    setEditAccountCode(item.account_code ?? "");
    setEditComment(item.review_comment ?? "");
  }

  function closeModal() {
    setSelected(null);
    setIsEditing(false);
    setDeleteConfirm(false);
    setActionError("");
  }

  async function handleSave() {
    if (!selected) return;
    setSaving(true);
    setActionError("");
    try {
      await updateReceiptReview(selected.receipt_id, {
        account_code: editAccountCode || undefined,
        review_comment: editComment || undefined,
      });
      // 목록 갱신 후 선택 항목도 업데이트
      const updated = await getReviewHistory();
      setItems(updated);
      const fresh = updated.find((i) => i.receipt_id === selected.receipt_id);
      if (fresh) {
        setSelected(fresh);
        setEditAccountCode(fresh.account_code ?? "");
        setEditComment(fresh.review_comment ?? "");
      }
      setIsEditing(false);
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "수정 실패");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!selected) return;
    setDeleting(true);
    setActionError("");
    try {
      await deleteReceipt(selected.receipt_id);
      setItems((prev) => prev.filter((i) => i.receipt_id !== selected.receipt_id));
      closeModal();
    } catch (e: unknown) {
      setActionError(e instanceof Error ? e.message : "삭제 실패");
      setDeleting(false);
    }
  }

  const fmt = (d: string | null) =>
    d ? new Date(d).toLocaleDateString("ko-KR", {
      year: "numeric", month: "long", day: "numeric",
      hour: "2-digit", minute: "2-digit",
    }) : "—";

  return (
    <main className="shell">
      <Sidebar active="history" />

      <section className="workspace">
        <header className="topbar">
          <div>
            <h1>처리 완료 목록</h1>
            <p>승인 또는 반려된 영수증 이력입니다. 행을 클릭하면 상세 내용을 확인할 수 있습니다.</p>
          </div>
        </header>

        {loading ? (
          <div className="loader">불러오는 중...</div>
        ) : error ? (
          <p style={{ color: "var(--danger)" }}>{error}</p>
        ) : items.length === 0 ? (
          <div className="emptyState">처리 완료된 영수증이 없습니다.</div>
        ) : (
          <table className="dataTable text-left" style={{ marginTop: 20 }}>
            <thead>
              <tr>
                {["ID", "파일명", "상태", "계정과목", "검토 의견", "처리일시"].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr
                  key={item.receipt_id}
                  onClick={() => openModal(item)}
                  style={{ cursor: "pointer" }}
                >
                  <td style={{ color: "var(--muted)" }}>#{item.receipt_id}</td>
                  <td style={{ fontWeight: 600 }}>{item.original_filename}</td>
                  <td>
                    <span className={`badge ${STATUS_BADGE[item.status] ?? "badge-muted"}`}>
                      {STATUS_LABEL[item.status] ?? item.status}
                    </span>
                  </td>
                  <td style={{ color: "var(--muted)" }}>{item.account_code ?? "—"}</td>
                  <td style={{ color: "var(--muted)", maxWidth: 200, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {item.review_comment ?? "—"}
                  </td>
                  <td style={{ color: "var(--muted)", whiteSpace: "nowrap" }}>
                    {fmt(item.reviewed_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      {/* 상세 모달 */}
      {selected && (
        <div className="modalBackdrop" onClick={closeModal}>
          <div
            className="modalPanel"
            onClick={(e) => e.stopPropagation()}
            style={{ width: 520, maxWidth: "90vw" }}
          >
            {/* 헤더 */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
              <div>
                <p style={{ color: "var(--muted)", fontSize: 12, margin: 0 }}>#{selected.receipt_id}</p>
                <h2 style={{ margin: "4px 0 0", fontSize: 18 }}>{selected.original_filename}</h2>
              </div>
              <button
                onClick={closeModal}
                style={{ background: "none", border: "none", fontSize: 20, cursor: "pointer", color: "var(--muted)", padding: "0 4px", boxShadow: "none" }}
              >✕</button>
            </div>

            {/* 상세 정보 */}
            <dl style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px 24px", marginBottom: 24 }}>
              {[
                ["상태", <span key="s" style={{ fontWeight: 700, color: STATUS_COLOR[selected.status] }}>{STATUS_LABEL[selected.status]}</span>],
                ["업로드일", fmt(selected.created_at)],
                ["거래일", selected.transaction_date ?? "—"],
                ["처리일시", fmt(selected.reviewed_at)],
              ].map(([label, value]) => (
                <div key={String(label)}>
                  <dt style={{ fontSize: 12, color: "var(--muted)", fontWeight: 600, marginBottom: 2 }}>{label}</dt>
                  <dd style={{ margin: 0, fontSize: 14 }}>{value}</dd>
                </div>
              ))}
            </dl>

            {/* 수정 폼 또는 정보 표시 */}
            {isEditing ? (
              <div style={{ display: "flex", flexDirection: "column", gap: 14, marginBottom: 20 }}>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)", display: "block", marginBottom: 4 }}>계정과목</label>
                  <input
                    value={editAccountCode}
                    onChange={(e) => setEditAccountCode(e.target.value)}
                    placeholder="예: 복리후생비"
                    style={{ width: "100%", padding: "8px 10px", border: "1px solid var(--line)", borderRadius: 6, fontSize: 14, boxSizing: "border-box" }}
                  />
                </div>
                <div>
                  <label style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)", display: "block", marginBottom: 4 }}>검토 의견</label>
                  <textarea
                    value={editComment}
                    onChange={(e) => setEditComment(e.target.value)}
                    placeholder="검토 의견을 입력하세요..."
                    rows={3}
                    style={{ width: "100%", padding: "8px 10px", border: "1px solid var(--line)", borderRadius: 6, fontSize: 14, resize: "vertical", fontFamily: "inherit", boxSizing: "border-box" }}
                  />
                </div>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 20 }}>
                <div>
                  <p style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)", margin: "0 0 4px" }}>계정과목</p>
                  <p style={{ margin: 0, fontSize: 14 }}>{selected.account_code ?? "—"}</p>
                </div>
                <div>
                  <p style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)", margin: "0 0 4px" }}>검토 의견</p>
                  <p style={{ margin: 0, fontSize: 14, whiteSpace: "pre-wrap" }}>{selected.review_comment ?? "—"}</p>
                </div>
              </div>
            )}

            {actionError && <p style={{ color: "var(--danger)", fontSize: 13, marginBottom: 12 }}>{actionError}</p>}

            {/* 액션 버튼 */}
            {deleteConfirm ? (
              <div style={{ background: "var(--danger-soft)", border: "1px solid #f6cdd8", borderRadius: "var(--r-md)", padding: "14px 16px" }}>
                <p style={{ margin: "0 0 12px", fontSize: 14, color: "#9f1239", fontWeight: 550 }}>정말 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.</p>
                <div style={{ display: "flex", gap: 8 }}>
                  <button className="btn-danger" onClick={handleDelete} disabled={deleting} style={{ flex: 1 }}>
                    {deleting ? "삭제 중..." : "삭제 확인"}
                  </button>
                  <button className="secondary" onClick={() => setDeleteConfirm(false)} style={{ flex: 1 }}>
                    취소
                  </button>
                </div>
              </div>
            ) : isEditing ? (
              <div style={{ display: "flex", gap: 8 }}>
                <button onClick={handleSave} disabled={saving} style={{ flex: 1 }}>
                  {saving ? "저장 중..." : "저장"}
                </button>
                <button className="secondary" onClick={() => { setIsEditing(false); setActionError(""); }} style={{ flex: 1 }}>
                  취소
                </button>
              </div>
            ) : (
              <div style={{ display: "flex", gap: 8 }}>
                <button className="secondary" onClick={() => downloadAuditCsv(selected.receipt_id)} style={{ flex: 1 }}>
                  CSV
                </button>
                <button onClick={() => setIsEditing(true)} style={{ flex: 1 }}>
                  수정
                </button>
                <button className="btn-ghost-danger" onClick={() => setDeleteConfirm(true)} style={{ flex: 1 }}>
                  삭제
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </main>
  );
}

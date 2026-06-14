"use client";

import { ReactNode } from "react";
import { logout } from "../../lib/api";

type NavKey = "reviews" | "history" | "tax-invoices" | "statements" | "reports";

const ICONS: Record<NavKey, ReactNode> = {
  reviews: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 12l2 2 4-4" />
      <path d="M21 12c0 1.66-4.03 3-9 3s-9-1.34-9-3" />
      <path d="M3 5v14c0 1.66 4.03 3 9 3s9-1.34 9-3V5" />
      <path d="M3 5c0 1.66 4.03 3 9 3s9-1.34 9-3-4.03-3-9-3-9 1.34-9 3" />
    </svg>
  ),
  history: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v5h5" />
      <path d="M3.05 13A9 9 0 1 0 6 5.3L3 8" />
      <path d="M12 7v5l3 2" />
    </svg>
  ),
  "tax-invoices": (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M8 13h8M8 17h5" />
    </svg>
  ),
  statements: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="5" width="20" height="14" rx="2" />
      <path d="M2 10h20" />
      <path d="M6 15h4" />
    </svg>
  ),
  reports: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 3v18h18" />
      <rect x="7" y="11" width="3" height="6" rx="0.5" />
      <rect x="12" y="7" width="3" height="10" rx="0.5" />
      <rect x="17" y="13" width="3" height="4" rx="0.5" />
    </svg>
  ),
};

const NAV: { key: NavKey; href: string; label: string }[] = [
  { key: "reviews", href: "/", label: "영수증 검토" },
  { key: "history", href: "/history", label: "처리 완료" },
  { key: "tax-invoices", href: "/tax-invoices", label: "세금계산서" },
  { key: "statements", href: "/statements", label: "카드내역" },
  { key: "reports", href: "/reports", label: "월별 리포트" },
];

export default function Sidebar({
  active,
  children,
}: {
  active: NavKey;
  children?: ReactNode;
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <span className="brand-mark" aria-hidden>
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 2 4 6v6c0 5 3.4 7.7 8 10 4.6-2.3 8-5 8-10V6z" />
            <path d="m9 12 2 2 4-4" />
          </svg>
        </span>
        <span>
          Tax-Copilot
          <span className="brand-sub">AI 세무 검토</span>
        </span>
      </div>

      <nav>
        {NAV.map((item) => (
          <a key={item.key} href={item.href} className={active === item.key ? "active" : undefined}>
            {ICONS[item.key]}
            {item.label}
          </a>
        ))}
        <div className="nav-sep" />
        <a onClick={logout}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <path d="m16 17 5-5-5-5" />
            <path d="M21 12H9" />
          </svg>
          로그아웃
        </a>
      </nav>

      {children}
    </aside>
  );
}

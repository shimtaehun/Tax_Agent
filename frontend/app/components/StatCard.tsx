"use client";

import { ReactNode } from "react";

export type Tone = "primary" | "success" | "warn" | "danger" | "info" | "neutral";

const S = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export const STAT_ICONS = {
  receipt: (
    <svg viewBox="0 0 24 24" {...S}>
      <path d="M4 2v20l2-1.5L8 22l2-1.5L12 22l2-1.5L16 22l2-1.5L20 22V2l-2 1.5L16 2l-2 1.5L12 2l-2 1.5L8 2 6 3.5z" />
      <path d="M8 8h8M8 12h8M8 16h5" />
    </svg>
  ),
  clock: (
    <svg viewBox="0 0 24 24" {...S}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  ),
  alert: (
    <svg viewBox="0 0 24 24" {...S}>
      <path d="M10.3 3.7 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.7a2 2 0 0 0-3.4 0Z" />
      <path d="M12 9v4M12 17h.01" />
    </svg>
  ),
  check: (
    <svg viewBox="0 0 24 24" {...S}>
      <path d="M22 11.1V12a10 10 0 1 1-5.9-9.1" />
      <path d="m9 11 3 3L22 4" />
    </svg>
  ),
  fileIn: (
    <svg viewBox="0 0 24 24" {...S}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M12 18v-6M9 15l3 3 3-3" />
    </svg>
  ),
  fileOut: (
    <svg viewBox="0 0 24 24" {...S}>
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <path d="M14 2v6h6" />
      <path d="M12 12v6M9 15l3-3 3 3" />
    </svg>
  ),
  coins: (
    <svg viewBox="0 0 24 24" {...S}>
      <circle cx="8" cy="8" r="6" />
      <path d="M18.09 10.37A6 6 0 1 1 10.34 18" />
      <path d="M7 6h1v4M16.71 13.88l.7.71-2.82 2.82" />
    </svg>
  ),
  trending: (
    <svg viewBox="0 0 24 24" {...S}>
      <path d="m22 7-8.5 8.5-5-5L2 17" />
      <path d="M16 7h6v6" />
    </svg>
  ),
  scale: (
    <svg viewBox="0 0 24 24" {...S}>
      <path d="M12 3v18M7 21h10M5 7h14l-3.5 6a3.5 3.5 0 0 1-7 0z" opacity="0" />
      <path d="M12 3v17M6 21h12M3 7h18M7 7l-4 7a4 4 0 0 0 8 0zM17 7l-4 7a4 4 0 0 0 8 0z" />
    </svg>
  ),
  calendar: (
    <svg viewBox="0 0 24 24" {...S}>
      <rect x="3" y="4" width="18" height="18" rx="2" />
      <path d="M16 2v4M8 2v4M3 10h18" />
    </svg>
  ),
  inbox: (
    <svg viewBox="0 0 24 24" {...S}>
      <path d="M22 12h-6l-2 3h-4l-2-3H2" />
      <path d="M5.5 5.1 2 12v6a2 2 0 0 0 2 2h16a2 2 0 0 0 2-2v-6l-3.5-6.9A2 2 0 0 0 16.8 4H7.2a2 2 0 0 0-1.7 1.1Z" />
    </svg>
  ),
} as const;

export type StatIconKey = keyof typeof STAT_ICONS;

export type StatDelta = {
  dir: "up" | "down";
  value: string;
  note?: string;
};

const DELTA_ARROW = {
  up: (
    <svg viewBox="0 0 24 24" {...S} aria-hidden>
      <path d="m6 15 6-6 6 6" />
    </svg>
  ),
  down: (
    <svg viewBox="0 0 24 24" {...S} aria-hidden>
      <path d="m6 9 6 6 6-6" />
    </svg>
  ),
};

export default function StatCard({
  label,
  value,
  icon,
  tone = "primary",
  hero = false,
  delta,
}: {
  label: string;
  value: ReactNode;
  icon: StatIconKey;
  tone?: Tone;
  hero?: boolean;
  delta?: StatDelta;
}) {
  return (
    <div className={`statCard rise tone-${tone}${hero ? " hero" : ""}`}>
      <div className="ic" aria-hidden>{STAT_ICONS[icon]}</div>
      <div>
        <div className="v">{value}</div>
        <div className="l">{label}</div>
        {delta && (
          <div className={`delta delta-${delta.dir}`}>
            {DELTA_ARROW[delta.dir]}
            {delta.value}
            {delta.note && <small>{delta.note}</small>}
          </div>
        )}
      </div>
    </div>
  );
}

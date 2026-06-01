"use client";

// 무의존성 경량 SVG 차트 (도넛 / 가로 막대)

export type Segment = { label: string; value: number; color: string };

export function DonutChart({
  segments,
  size = 168,
  thickness = 24,
  centerLabel,
  centerValue,
  format = (n: number) => n.toLocaleString("ko-KR"),
}: {
  segments: Segment[];
  size?: number;
  thickness?: number;
  centerLabel?: string;
  centerValue?: string;
  format?: (n: number) => string;
}) {
  const total = segments.reduce((s, x) => s + Math.max(0, x.value), 0);
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  let acc = 0;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 22, flexWrap: "wrap" }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ flexShrink: 0 }}>
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--bg-soft)" strokeWidth={thickness} />
          {total > 0 &&
            segments.map((s, i) => {
              const frac = Math.max(0, s.value) / total;
              const len = frac * c;
              const dash = `${len} ${c - len}`;
              const offset = -acc * c;
              acc += frac;
              return (
                <circle
                  key={i}
                  cx={size / 2}
                  cy={size / 2}
                  r={r}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={thickness}
                  strokeDasharray={dash}
                  strokeDashoffset={offset}
                  strokeLinecap="round"
                />
              );
            })}
        </g>
        {centerValue && (
          <text x="50%" y="47%" textAnchor="middle" dominantBaseline="middle"
            style={{ fontSize: 21, fontWeight: 800, fill: "var(--ink)", fontVariantNumeric: "tabular-nums" }}>
            {centerValue}
          </text>
        )}
        {centerLabel && (
          <text x="50%" y="60%" textAnchor="middle" dominantBaseline="middle"
            style={{ fontSize: 11, fontWeight: 600, fill: "var(--muted)" }}>
            {centerLabel}
          </text>
        )}
      </svg>

      <div className="legend">
        {segments.map((s, i) => (
          <div className="legend-item" key={i}>
            <span className="legend-dot" style={{ background: s.color }} />
            <span className="legend-label">{s.label}</span>
            <span className="legend-val">{format(s.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export type Bar = { label: string; value: number; color: string };

export function BarList({
  items,
  format = (n: number) => n.toLocaleString("ko-KR"),
}: {
  items: Bar[];
  format?: (n: number) => string;
}) {
  const max = Math.max(1, ...items.map((i) => Math.abs(i.value)));
  return (
    <div className="barList">
      {items.map((b, i) => (
        <div className="barRow" key={i}>
          <div className="barHead">
            <span className="barLabel">{b.label}</span>
            <span className="barVal">{format(b.value)}</span>
          </div>
          <div className="barTrack">
            <div
              className="barFill rise"
              style={{ width: `${(Math.abs(b.value) / max) * 100}%`, background: b.color }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

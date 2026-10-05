import { useEffect, useState } from "react";
import { API } from "./api";

export interface Area {
  pcode: string;
  name: string;
  state: string;
}

interface TrendPoint {
  period: string;
  spills: number;
  spills_with_volume: number;
  reported_bbl: number;
  spills_rolling_avg_3: number;
  partial?: boolean;
}

const W = 336;
const H = 168;
const M = { top: 10, right: 6, bottom: 22, left: 34 };
const BAR = "#a8521e";
const LINE = "#2a78d6";

// Rounds up to 1, 2 or 5 times a power of ten so the ticks are clean numbers.
function niceMax(v: number): number {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  return [1, 2, 5, 10].map((m) => m * p).find((n) => n >= v)!;
}

// Column with a 4px rounded top and a square base.
function barPath(x: number, y: number, w: number, h: number): string {
  if (h <= 0) return "";
  const r = Math.min(4, w / 2, h);
  return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
}

export default function TrendChart({ area, onClear }: { area: Area | null; onClear: () => void }) {
  const [points, setPoints] = useState<TrendPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [hover, setHover] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    const q = area ? `?lga=${encodeURIComponent(area.pcode)}` : "";
    fetch(`${API}/trends${q}`)
      .then((r) => r.json())
      .then((d) => setPoints(d.series))
      .finally(() => setLoading(false));
  }, [area]);

  const iw = W - M.left - M.right;
  const ih = H - M.top - M.bottom;
  const max = niceMax(Math.max(1, ...points.map((p) => Math.max(p.spills, p.spills_rolling_avg_3))));
  const slot = points.length ? iw / points.length : iw;
  const bw = Math.min(24, Math.max(2, slot - 2));
  const x = (i: number) => M.left + i * slot + (slot - bw) / 2;
  const y = (v: number) => M.top + ih - (v / max) * ih;
  const line = points.map((p, i) => `${x(i) + bw / 2},${y(p.spills_rolling_avg_3)}`).join(" ");
  const h = hover !== null ? points[hover] : null;
  const total = points.reduce((s, p) => s + p.spills, 0);

  return (
    <section className="trend">
      <div className="trend-head">
        <div>
          <h3>Spills per year</h3>
          <p className="trend-area">
            {area ? `${area.name} LGA, ${area.state}` : "All areas. Click an LGA on the map to narrow it down."}
          </p>
        </div>
        {area && (
          <button className="link" onClick={onClear}>
            Show all
          </button>
        )}
      </div>

      <div className="trend-plot" style={{ opacity: loading ? 0.5 : 1 }}>
        <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" aria-label={`Usable spill reports per year, ${total} in total`}>
          {[0, max / 2, max].map((t) => (
            <g key={t}>
              <line x1={M.left} x2={W - M.right} y1={y(t)} y2={y(t)} className="grid" />
              <text x={M.left - 6} y={y(t)} className="tick" textAnchor="end" dominantBaseline="middle">
                {t.toLocaleString()}
              </text>
            </g>
          ))}
          {points.map((p, i) => (
            <path
              key={p.period}
              d={barPath(x(i), y(p.spills), bw, M.top + ih - y(p.spills))}
              fill={BAR}
              opacity={p.partial ? 0.35 : hover === i ? 0.75 : 1}
            />
          ))}
          {points.length > 1 && (
            <polyline points={line} fill="none" stroke={LINE} strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
          )}
          {points.map((p, i) =>
            Number(p.period) % 5 === 0 ? (
              <text key={p.period} x={x(i) + bw / 2} y={H - 6} className="tick" textAnchor="middle">
                {p.period}
              </text>
            ) : null,
          )}
          {points.map((p, i) => (
            <rect
              key={p.period}
              x={M.left + i * slot}
              y={M.top}
              width={slot}
              height={ih}
              fill="transparent"
              tabIndex={0}
              aria-label={`${p.period}: ${p.spills} spills`}
              onMouseEnter={() => setHover(i)}
              onMouseLeave={() => setHover(null)}
              onFocus={() => setHover(i)}
              onBlur={() => setHover(null)}
            />
          ))}
        </svg>

        {h && hover !== null && (
          <div
            className="trend-tip"
            style={{ left: Math.min(Math.max(x(hover) + bw / 2 - 80, 0), W - 160), top: 0 }}
          >
            <div className="tip-title">
              {h.period}
              {h.partial ? " (so far)" : ""}
            </div>
            <div className="tip-row">
              <span className="key bar" /> <strong>{h.spills}</strong> spills
            </div>
            <div className="tip-row">
              <span className="key line" /> <strong>{h.spills_rolling_avg_3}</strong> 3-year average
            </div>
            <div className="tip-row muted">
              {h.spills_with_volume} with a volume, {Math.round(h.reported_bbl).toLocaleString()} bbl reported
            </div>
          </div>
        )}
      </div>

      <div className="trend-legend">
        <span>
          <span className="key bar" /> Spills
        </span>
        <span>
          <span className="key line" /> 3-year average
        </span>
        <span className="muted">Pale bar: year so far</span>
      </div>
      <p className="trend-note">
        Usable reports in the register, not every spill. Reporting practice changed over time.
      </p>

      <details>
        <summary>Show as table</summary>
        <table className="trend-table">
          <thead>
            <tr>
              <th>Year</th>
              <th>Spills</th>
              <th>3-yr avg</th>
              <th>Reported bbl</th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.period}>
                <td>
                  {p.period}
                  {p.partial ? "*" : ""}
                </td>
                <td>{p.spills}</td>
                <td>{p.spills_rolling_avg_3}</td>
                <td>{Math.round(p.reported_bbl).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}

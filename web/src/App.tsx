import { useEffect, useRef, useState } from "react";
import maplibregl, { Map as MlMap } from "maplibre-gl";
import { API, EXPLAIN_QUERY, Explanation, gql, Summary, SUMMARY_QUERY } from "./api";
import TrendChart, { Area } from "./TrendChart";

type Shading = "spills" | "mangrove";

// OpenFreeMap: free vector tiles from OpenStreetMap data, no API key.
const BASEMAP = "https://tiles.openfreemap.org/styles/positron";

// Colour stops shared by the map fill and its key: [value, colour, label].
type Stop = [number, string, string];
const SPILL_STOPS: Stop[] = [
  [0, "#f3efe6", "0"], [10, "#e8c9a0", "10"], [50, "#d4914f", "50"],
  [200, "#a8521e", "200"], [800, "#5c2408", "800+"],
];
const MANGROVE_STOPS: Stop[] = [
  [-10, "#8c2d04", "-10%"], [-3, "#e6a26b", "-3%"], [0, "#f3efe6", "0"],
  [3, "#7fbf8f", "+3%"], [10, "#1b6b3a", "+10%"],
];
const ramp = (stops: Stop[]) => stops.flatMap(([v, c]) => [v, c]);

const SPILL_FILL = [
  "interpolate", ["linear"], ["get", "spills"], ...ramp(SPILL_STOPS),
] as maplibregl.ExpressionSpecification;
// LGAs with no mangrove in 2007 get the neutral colour.
const MANGROVE_FILL = [
  "interpolate", ["linear"],
  ["case", [">", ["get", "mangrove_ha_2007"], 0],
    ["*", 100, ["/", ["-", ["get", "mangrove_ha_2020"], ["get", "mangrove_ha_2007"]], ["get", "mangrove_ha_2007"]]],
    0],
  ...ramp(MANGROVE_STOPS),
] as maplibregl.ExpressionSpecification;

function ColourKey({ shading }: { shading: Shading }) {
  const stops = shading === "spills" ? SPILL_STOPS : MANGROVE_STOPS;
  return (
    <div className="colour-key">
      <div className="key-title">
        {shading === "spills" ? "Usable spill reports per LGA" : "Change in mangrove area, 2007 to 2020"}
      </div>
      <div className="key-bar" style={{ background: `linear-gradient(to right, ${stops.map((s) => s[1]).join(", ")})` }} />
      <div className="key-labels">
        {stops.map((s) => <span key={s[2]}>{s[2]}</span>)}
      </div>
      {shading === "mangrove" && (
        <div className="key-ends"><span>Lost</span><span>Pale: no change or no mangrove</span><span>Gained</span></div>
      )}
    </div>
  );
}

export default function App() {
  const mapEl = useRef<HTMLDivElement>(null);
  const map = useRef<MlMap | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [shading, setShading] = useState<Shading>("spills");
  const [selected, setSelected] = useState<Explanation | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [area, setArea] = useState<Area | null>(null);

  useEffect(() => {
    gql<{ summary: Summary }>(SUMMARY_QUERY).then((d) => setSummary(d.summary)).catch((e) => setError(String(e)));
  }, []);

  useEffect(() => {
    if (!mapEl.current || map.current) return;
    const m = new maplibregl.Map({
      container: mapEl.current,
      style: BASEMAP,
      center: [6.4, 5.0],
      zoom: 7.2,
    });
    map.current = m;
    // Exposed in development for browser-driven checks.
    if (import.meta.env.DEV) (window as unknown as { __map: MlMap }).__map = m;
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");

    m.on("load", () => {
      m.addSource("lgas", { type: "geojson", data: `${API}/geojson/lgas` });
      m.addLayer({
        id: "lga-fill", type: "fill", source: "lgas",
        paint: { "fill-color": SPILL_FILL, "fill-opacity": 0.75 },
      });
      m.addLayer({
        id: "lga-line", type: "line", source: "lgas",
        paint: { "line-color": "#ffffff", "line-width": 0.6 },
      });
      m.addLayer({
        id: "lga-selected", type: "line", source: "lgas",
        paint: { "line-color": "#1f1f1f", "line-width": 2 },
        filter: ["==", ["get", "pcode"], ""],
      });

      m.addSource("spills", { type: "geojson", data: `${API}/geojson/spills` });
      m.addLayer({
        id: "spills", type: "circle", source: "spills",
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["zoom"], 6, 1.6, 11, 5],
          // Corrected or flagged locations are drawn hollow so they read as less certain.
          "circle-color": ["case", ["==", ["get", "method"], "reported"], "#1f1f1f", "#ffffff"],
          "circle-stroke-color": "#1f1f1f",
          "circle-stroke-width": ["case", [">", ["get", "warnings"], 0], 1, 0.3],
          "circle-opacity": 0.75,
        },
      });

      const popup = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
      m.on("mousemove", "lga-fill", (e) => {
        const p = e.features?.[0]?.properties;
        if (!p) return;
        popup.setLngLat(e.lngLat).setHTML(
          `<strong>${p.name}</strong>, ${p.state}<br/>${p.spills} spills · ` +
            `${Math.round(p.mangrove_ha_2020).toLocaleString()} ha mangrove (2020)`,
        ).addTo(m);
      });
      m.on("mouseleave", "lga-fill", () => popup.remove());

      // Clicking an LGA (but not a spill inside it) shows that LGA's trend.
      m.on("click", "lga-fill", (e) => {
        if (m.queryRenderedFeatures(e.point, { layers: ["spills"] }).length) return;
        const p = e.features?.[0]?.properties;
        if (p) setArea({ pcode: p.pcode, name: p.name, state: p.state });
      });

      m.on("click", "spills", async (e) => {
        const id = e.features?.[0]?.properties?.id;
        if (!id) return;
        try {
          const d = await gql<{ explainSpill: Explanation }>(EXPLAIN_QUERY, { id: String(id) });
          setSelected(d.explainSpill);
        } catch (err) {
          setError(String(err));
        }
      });
      m.on("mouseenter", "spills", () => (m.getCanvas().style.cursor = "pointer"));
      m.on("mouseleave", "spills", () => (m.getCanvas().style.cursor = ""));
    });
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m || !m.getLayer("lga-selected")) return;
    m.setFilter("lga-selected", ["==", ["get", "pcode"], area?.pcode ?? ""]);
  }, [area]);

  useEffect(() => {
    const m = map.current;
    if (!m || !m.getLayer("lga-fill")) return;
    m.setPaintProperty("lga-fill", "fill-color", shading === "spills" ? SPILL_FILL : MANGROVE_FILL);
  }, [shading]);

  return (
    <div className="layout">
      <aside className="panel">
        <header>
          <h1>Sheen</h1>
          <p className="lede">
            Nigeria's official oil spill reports for the Niger Delta, checked for errors and
            mapped.
          </p>
        </header>

        {summary && (
          <dl className="stats">
            <div><dt>Reports {summary.windowStart.slice(0, 4)}–{summary.windowEnd.slice(0, 4)}</dt>
              <dd>{summary.reportsInWindow.toLocaleString()}</dd></div>
            <div><dt>Usable for analysis</dt>
              <dd>{Math.round((100 * summary.analysable) / summary.reportsInWindow)}%</dd></div>
            <div><dt>Reported volume</dt>
              <dd>{Math.round(summary.reportedBbl / 1000).toLocaleString()}k bbl</dd></div>
          </dl>
        )}

        <fieldset className="toggle">
          <legend>Shade LGAs by</legend>
          <label><input type="radio" checked={shading === "spills"} onChange={() => setShading("spills")} />
            Spill count</label>
          <label><input type="radio" checked={shading === "mangrove"} onChange={() => setShading("mangrove")} />
            Mangrove change 2007–2020</label>
        </fieldset>

        <ColourKey shading={shading} />

        <p className="legend">
          <span className="dot solid" /> reported location <span className="dot hollow" /> corrected location
        </p>

        <TrendChart area={area} onClear={() => setArea(null)} />

        {error && <p className="error">{error}</p>}

        {selected ? (
          <section className="detail">
            <h2>Report {selected.spill.id}</h2>
            <p className="meta">
              {selected.spill.operator ?? "Unknown operator"} · {selected.spill.incidentDate ?? "no date"}
              {selected.spill.causeLabel && <> · {selected.spill.causeLabel}</>}
              {selected.spill.quantityBbl != null && <> · {selected.spill.quantityBbl} bbl</>}
            </p>
            {selected.spill.siteName && <p className="site">{selected.spill.siteName}</p>}

            <h3>How this record was treated</h3>
            <ol className="steps">
              {selected.steps.map((s, i) => (
                <li key={i}><span className="step">{s.step}</span>{s.outcome}</li>
              ))}
            </ol>

            {selected.spill.issues.length > 0 && (
              <>
                <h3>Issues</h3>
                <ul className="issues">
                  {selected.spill.issues.map((i, n) => (
                    <li key={`${i.code}-${n}`} className={i.severity}>
                      <code>{i.code}</code> {i.message}
                    </li>
                  ))}
                </ul>
              </>
            )}

            <details>
              <summary>Raw record as published</summary>
              <pre>{JSON.stringify(selected.rawRecord, null, 2)}</pre>
            </details>
          </section>
        ) : (
          <p className="hint">Click a spill to see how its record was checked and placed.</p>
        )}

      </aside>
      <div ref={mapEl} className="map" />
    </div>
  );
}

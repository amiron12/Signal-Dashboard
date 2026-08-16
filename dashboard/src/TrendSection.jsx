import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Corners } from "./Cube.jsx";

// One chart, three series. The histories are already loaded, so switching is
// client-side only — no refetch.
const METRICS = [
  {
    key: "load",
    label: "Page load time",
    receiver: "seo_onpage",
    value: (s) => s.page_load_time_ms,
  },
  {
    key: "geo",
    label: "GEO coverage",
    receiver: "geo_readiness",
    // How many of the three answer-engine types the sample carried, 0–3.
    value: (s) =>
      s.answer_schema_pages &&
      Object.values(s.answer_schema_pages).filter((n) => n > 0).length,
  },
  {
    key: "news",
    label: "Mentions",
    receiver: "news_mentions",
    value: (s) => s.mention_count,
  },
];

// Runs where the signal is missing are dropped rather than plotted as 0 —
// "we measured nothing" isn't the same as "there was nothing".
function seriesFor(history, value) {
  return history
    .filter((e) => e.status === "ok")
    .map((e) => ({
      timestamp: new Date(e.timestamp).toLocaleString(),
      value: value(e.signals),
    }))
    .filter((point) => point.value !== null && point.value !== undefined);
}

export default function TrendSection({ histories }) {
  const [activeMetric, setActiveMetric] = useState("load");

  const metric = METRICS.find((m) => m.key === activeMetric);
  const data = seriesFor(histories[metric.receiver] ?? [], metric.value);

  return (
    <section className="trend">
      <div className="trend-head">
        <div className="band-kicker">Trend</div>
        <div className="seg">
          {METRICS.map((m) => (
            <button
              key={m.key}
              type="button"
              className={`seg-opt ${m.key === activeMetric ? "active" : ""}`}
              onClick={() => setActiveMetric(m.key)}
            >
              {m.label}
            </button>
          ))}
        </div>
      </div>

      <div className="card blueprint">
        <Corners />
        {data.length < 2 ? (
          <p className="band-note">Not enough runs yet to draw a trend.</p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Line type="monotone" dataKey="value" name={metric.label} stroke="var(--color-accent-700)" />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}

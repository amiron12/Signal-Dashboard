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

// The six signals worth a trend line. `key` is the signal's own name in the
// receiver payload — the cards tag the matching box with the same string, and
// that string is the whole selection protocol. All six are plain numbers, so
// there's nothing to compute: the key is the lookup.
//
// A percentage gets a fixed 0–100 axis. The others are left to autoscale,
// which is right for an open-ended count but wrong for a percent: autoscaling
// 21%–23% to fill the panel makes a two-point wobble look like a collapse,
// when the real story is that coverage is stuck near the bottom of its range.
const METRICS = [
  { key: "title_length", label: "Title length", receiver: "seo_onpage" },
  { key: "meta_description_length", label: "Meta description length", receiver: "seo_onpage" },
  { key: "alt_coverage_pct", label: "Alt-text coverage", receiver: "seo_onpage", domain: [0, 100], unit: "%" },
  { key: "page_load_time_ms", label: "Page load time", receiver: "seo_onpage" },
  { key: "faq_headings_sampled", label: "Q&A headings", receiver: "geo_readiness" },
  { key: "mention_count", label: "Mentions", receiver: "news_mentions" },
];

// Runs where the signal is missing are dropped rather than plotted as 0 —
// "we measured nothing" isn't the same as "there was nothing".
function seriesFor(history, key) {
  return history
    .filter((e) => e.status === "ok")
    .map((e) => ({
      timestamp: new Date(e.timestamp).toLocaleString(),
      value: e.signals[key],
    }))
    .filter((point) => point.value !== null && point.value !== undefined);
}

// Nothing here until a signal's chart icon is pressed. The histories are all
// loaded already, so opening and switching is client-side only — no refetch.
export default function TrendSection({ histories, activeMetric }) {
  const metric = METRICS.find((m) => m.key === activeMetric);
  if (!metric) return null;

  const data = seriesFor(histories[metric.receiver] ?? [], metric.key);

  return (
    <section className="trend">
      <div className="band-kicker">Trend — {metric.label}</div>

      <div className="card blueprint">
        <Corners />
        {data.length < 2 ? (
          <p className="band-note">Not enough runs yet to draw a trend.</p>
        ) : (
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" />
              <YAxis allowDecimals={false} domain={metric.domain ?? [0, "auto"]} unit={metric.unit} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="value"
                name={metric.label}
                unit={metric.unit}
                stroke="var(--color-accent-700)"
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}

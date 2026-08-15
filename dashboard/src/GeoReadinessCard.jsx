import { useEffect, useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { getHistory } from "./api.js";

// One row per signal to display, same pattern as SeoOnpageCard. `format` is
// optional — it only runs when the signal isn't null, so it never has to
// handle the "this check failed" case itself.
const SIGNAL_ROWS = [
  {
    key: "schema_types_found",
    label: "Schema types found",
    format: (v) => (v.length > 0 ? v.join(", ") : "none"),
  },
  { key: "faq_heading_count", label: "FAQ-style headings" },
  { key: "llms_txt_present", label: "llms.txt present" },
  { key: "wikipedia_entry_exists", label: "Wikipedia entry exists" },
  {
    key: "sitemap_url_count",
    label: "Pages in sitemap",
    format: (v) => v.toLocaleString(),
  },
  { key: "pages_updated_last_30d", label: "Pages updated (last 30d)" },
  { key: "pct_stale_over_1y", label: "Dated pages over a year old", suffix: "%" },
  {
    key: "content_type_coverage",
    label: "Content types",
    format: (v) =>
      Object.entries(v)
        .filter(([, count]) => count > 0)
        .map(([label, count]) => `${label} ${count}`)
        .join(", ") || "none",
  },
  {
    key: "answer_schema_pages",
    label: "Answer-engine markup (sampled pages)",
    format: (v) =>
      Object.entries(v)
        .map(([type, count]) => `${type} ${count}`)
        .join(", "),
  },
  {
    key: "pct_sampled_with_answer_schema",
    label: "Sampled pages with any of it",
    suffix: "%",
  },
  { key: "pages_sampled", label: "Pages sampled" },
];

// A signal is null when its check failed, or when the site genuinely has
// nothing to report (e.g. a sitemap with no <lastmod>). Both read as unknown.
function formatSignal(value, format, suffix) {
  if (value === null || value === undefined) return "unknown";
  return (format ? format(value) : String(value)) + (suffix ?? "");
}

export default function GeoReadinessCard({ company, refreshKey }) {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (!company) return;
    getHistory(company, "geo_readiness").then(setHistory);
  }, [company, refreshKey]);

  const latest = history.length > 0 ? history[history.length - 1] : null;

  // Charting answer-engine markup coverage: it's the point of this receiver.
  // Runs where the sample came back empty are dropped rather than plotted as
  // 0 — "we measured nothing" isn't the same as "the site has nothing".
  const chartData = history
    .filter((e) => e.status === "ok")
    .filter((e) => e.signals.pct_sampled_with_answer_schema != null)
    .map((e) => ({
      timestamp: new Date(e.timestamp).toLocaleString(),
      pct_sampled_with_answer_schema: e.signals.pct_sampled_with_answer_schema,
    }));

  return (
    <section style={{ marginTop: "2rem" }}>
      <h2>GEO readiness</h2>

      {!latest && <p>No runs yet. Click "Scan now".</p>}

      {latest && latest.status === "error" && (
        <p style={{ color: "red" }}>Last run failed: {latest.error_message}</p>
      )}

      {latest && latest.status === "ok" && (
        <table style={{ borderCollapse: "collapse" }}>
          <tbody>
            {SIGNAL_ROWS.map(({ key, label, format, suffix }) => (
              <tr key={key}>
                <td style={{ padding: "0.25rem 1rem 0.25rem 0", color: "#555" }}>
                  {label}
                </td>
                <td style={{ padding: "0.25rem 0" }}>
                  {formatSignal(latest.signals[key], format, suffix)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {latest?.signals?.sitemap_scan_truncated && (
        <p style={{ color: "#888", fontSize: "0.85rem" }}>
          Stopped after reading {latest.signals.sitemap_files_read} sitemap files
          — the counts above are a lower bound.
        </p>
      )}

      {chartData.length > 1 && (
        <div>
          <h3>Answer-engine markup coverage over time</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="pct_sampled_with_answer_schema"
                stroke="#c026d3"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}

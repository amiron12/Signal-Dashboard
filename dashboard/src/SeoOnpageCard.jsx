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

// One row per signal to display. Add a new signal to the receiver, then add
// a row here to show it — same "list of small pieces" pattern as the backend.
const SIGNAL_ROWS = [
  { key: "title_present", label: "Title present" },
  { key: "title_length", label: "Title length" },
  { key: "meta_description_present", label: "Meta description present" },
  { key: "meta_description_length", label: "Meta description length" },
  { key: "h1_count", label: "H1 count" },
  { key: "alt_coverage_pct", label: "Alt-text coverage", suffix: "%" },
  { key: "jsonld_present", label: "JSON-LD present" },
  { key: "page_load_time_ms", label: "Page load time", suffix: " ms" },
];

export default function SeoOnpageCard({ company, refreshKey }) {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (!company) return;
    getHistory(company, "seo_onpage").then(setHistory);
  }, [company, refreshKey]);

  const latest = history.length > 0 ? history[history.length - 1] : null;

  const chartData = history
    .filter((e) => e.status === "ok")
    .map((e) => ({
      timestamp: new Date(e.timestamp).toLocaleString(),
      page_load_time_ms: e.signals.page_load_time_ms ?? 0,
    }));

  return (
    <section style={{ marginTop: "2rem" }}>
      <h2>SEO on-page</h2>

      {!latest && <p>No runs yet. Click "Scan now".</p>}

      {latest && latest.status === "error" && (
        <p style={{ color: "red" }}>Last run failed: {latest.error_message}</p>
      )}

      {latest && latest.status === "ok" && (
        <table style={{ borderCollapse: "collapse" }}>
          <tbody>
            {SIGNAL_ROWS.map(({ key, label, suffix }) => (
              <tr key={key}>
                <td style={{ padding: "0.25rem 1rem 0.25rem 0", color: "#555" }}>
                  {label}
                </td>
                <td style={{ padding: "0.25rem 0" }}>
                  {String(latest.signals[key])}
                  {suffix ?? ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {chartData.length > 1 && (
        <div>
          <h3>Page load time over time</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Line type="monotone" dataKey="page_load_time_ms" stroke="#16a34a" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}

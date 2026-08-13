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

export default function NewsMentionsCard({ company, refreshKey }) {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    if (!company) return;
    getHistory(company, "news_mentions").then(setHistory);
  }, [company, refreshKey]);

  const latest = history.length > 0 ? history[history.length - 1] : null;

  const chartData = history
    .filter((e) => e.status === "ok")
    .map((e) => ({
      timestamp: new Date(e.timestamp).toLocaleString(),
      mention_count: e.signals.mention_count ?? 0,
    }));

  return (
    <section style={{ marginTop: "2rem" }}>
      <h2>News mentions</h2>

      {!latest && <p>No runs yet. Click "Scan now".</p>}

      {latest && latest.status === "error" && (
        <p style={{ color: "red" }}>Last run failed: {latest.error_message}</p>
      )}

      {latest && latest.status === "ok" && (
        <div>
          <p>Mentions in lookback window: {latest.signals.mention_count}</p>
          <ul>
            {latest.signals.mentions.map((m, i) => (
              <li key={i}>
                <a href={m.link} target="_blank" rel="noreferrer">
                  {m.headline}
                </a>{" "}
                <span style={{ color: "#888" }}>
                  ({new Date(m.published).toLocaleDateString()})
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {chartData.length > 1 && (
        <div>
          <h3>Mention count over time</h3>
          <ResponsiveContainer width="100%" height={250}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="timestamp" />
              <YAxis allowDecimals={false} />
              <Tooltip />
              <Line type="monotone" dataKey="mention_count" stroke="#4f46e5" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}

import { Corners } from "./Cube.jsx";

export default function NewsMentionsCard({ history }) {
  const latest = history.length > 0 ? history[history.length - 1] : null;

  return (
    <section>
      <div className="band-kicker">News mentions</div>

      <div className="card blueprint">
        <Corners />

        {!latest && <p className="band-note">No runs yet. Click "Scan now".</p>}

        {latest && latest.status === "error" && (
          <p className="band-note" style={{ color: "var(--status-bad)" }}>
            Last run failed: {latest.error_message}
          </p>
        )}

        {latest && latest.status === "ok" && (
          <>
            <div className="news-count">
              <div className="cube-value">{latest.signals.mention_count}</div>
              <div className="cube-label">mentions this week</div>
            </div>

            <div className="news-list">
              {latest.signals.mentions.map((m, i) => (
                <div className="news-item" key={i}>
                  <a href={m.link} target="_blank" rel="noreferrer">
                    {m.headline}
                  </a>
                  <div className="news-date">
                    {new Date(m.published).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </section>
  );
}

import { Cube, CubeGrid, higherIsBetter, lowerIsBetter } from "./Cube.jsx";

// One cube per signal. Same data keys as before — only the rendering changed.
// Title/meta pair their present/length signals into a single cube: presence
// picks the color, length is shown underneath as information.
function seoCubes(s) {
  return [
    {
      label: "Title",
      sub: s.title_present ? `${s.title_length} characters` : "Missing",
      status: s.title_present ? "good" : "bad",
    },
    {
      label: "Meta",
      sub: s.meta_description_present
        ? `${s.meta_description_length} characters`
        : "Missing",
      status: s.meta_description_present ? "good" : "bad",
    },
    {
      label: "H1 count",
      value: s.h1_count,
      status: s.h1_count === 1 ? "good" : s.h1_count === 2 ? "warn" : "bad",
    },
    {
      label: "Alt-text coverage",
      value: `${s.alt_coverage_pct}%`,
      status: higherIsBetter(s.alt_coverage_pct, 90, 60),
    },
    // Binary: no value at all, the color is the whole answer.
    { label: "JSON-LD", status: s.jsonld_present ? "good" : "bad" },
    {
      label: "Page load time",
      value: `${Math.round(s.page_load_time_ms)}ms`,
      status: lowerIsBetter(s.page_load_time_ms, 800, 1500),
    },
  ];
}

export default function SeoOnpageCard({ history }) {
  const latest = history.length > 0 ? history[history.length - 1] : null;

  return (
    <section>
      <div className="band-kicker">SEO on-page</div>

      {!latest && <p className="band-note">No runs yet. Click "Scan now".</p>}

      {latest && latest.status === "error" && (
        <p className="band-note" style={{ color: "var(--status-bad)" }}>
          Last run failed: {latest.error_message}
        </p>
      )}

      {latest && latest.status === "ok" && (
        <CubeGrid>
          {seoCubes(latest.signals).map((c) => (
            <Cube key={c.label} {...c} />
          ))}
        </CubeGrid>
      )}
    </section>
  );
}

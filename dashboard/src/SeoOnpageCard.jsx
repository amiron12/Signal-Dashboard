import { Cube, CubeGrid, binary, scored, higherIsBetter, lowerIsBetter } from "./Cube.jsx";

// Title/meta pair their present/length signals into a single cube: presence
// picks the color, length is shown underneath as information. Absent means we
// measured the page and found none; a signal we don't have at all is a
// different statement, and `scored`/`binary` render that as "unknown".
function pair(label, present, length) {
  if (present === null || present === undefined) return { label, value: "unknown" };
  return {
    label,
    sub: present ? `${length} characters` : "Missing",
    status: present ? "good" : "bad",
  };
}

// One cube per signal. Every one goes through a helper that handles the
// missing case, so a cube added later can't paint red on runs that predate it.
//
// A `metric` is the signal's key in the payload, added to the cubes that carry
// a trend — that's what puts a chart icon on them. It's spread on afterwards
// rather than passed into the helpers, so the helpers stay as they were and a
// cube reading "unknown" keeps its icon (its history is still worth a look).
function seoCubes(s) {
  return [
    { ...pair("Title", s.title_present, s.title_length), metric: "title_length" },
    {
      ...pair("Meta", s.meta_description_present, s.meta_description_length),
      metric: "meta_description_length",
    },
    scored("H1 count", s.h1_count, (v) => v, (v) =>
      v === 1 ? "good" : v === 2 ? "warn" : "bad"
    ),
    {
      ...scored("Alt-text coverage", s.alt_coverage_pct, (v) => `${v}%`, (v) =>
        higherIsBetter(v, 90, 60)
      ),
      metric: "alt_coverage_pct",
    },
    // Binary: no value at all, the color is the whole answer.
    binary("JSON-LD", s.jsonld_present),
    binary("robots.txt", s.robots_txt_present),
    {
      ...scored("Page load time", s.page_load_time_ms, (v) => `${Math.round(v)}ms`, (v) =>
        lowerIsBetter(v, 800, 1500)
      ),
      metric: "page_load_time_ms",
    },
  ];
}

export default function SeoOnpageCard({ history, activeMetric, onToggleMetric }) {
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
            <Cube
              key={c.label}
              {...c}
              activeMetric={activeMetric}
              onToggleMetric={onToggleMetric}
            />
          ))}
        </CubeGrid>
      )}
    </section>
  );
}

import { Cube, CubeGrid, scored } from "./Cube.jsx";

// Binary check: the color is the whole answer, so the cube shows its label
// only — unless the check failed, which has to say so.
function binary(label, value) {
  if (value === null || value === undefined) return { label, value: "unknown" };
  return { label, status: value ? "good" : "bad" };
}

// The only three Schema.org types this dashboard cares about — the ones
// answer engines quote. One cube each: did the sampled content pages carry
// it or not.
const ANSWER_TYPES = ["Article", "FAQPage", "HowTo"];

function schemaTypeCube(type, byType) {
  return binary(type, byType ? (byType[type] ?? 0) > 0 : null);
}

// Same signal keys as the old table — `scored` handles the null case for all
// of them, so no formatter here has to think about a failed check.
function geoCubes(s) {
  return [
    ...ANSWER_TYPES.map((t) => schemaTypeCube(t, s.answer_schema_pages)),
    scored("Q&A headings", s.faq_headings_sampled, (v) => v, (v) =>
      v >= 1 ? "good" : "bad"
    ),
    binary("llms.txt present", s.llms_txt_present),
    binary("Wikipedia entry", s.wikipedia_entry_exists),
    scored("Pages in sitemap", s.sitemap_url_count, (v) => v.toLocaleString()),
    scored("Updated (30d)", s.pages_updated_last_30d, (v) => v.toLocaleString()),
  ];
}

export default function GeoReadinessCard({ history }) {
  const latest = history.length > 0 ? history[history.length - 1] : null;

  return (
    <section>
      <div className="band-kicker">GEO readiness</div>

      {!latest && <p className="band-note">No runs yet. Click "Scan now".</p>}

      {latest && latest.status === "error" && (
        <p className="band-note" style={{ color: "var(--status-bad)" }}>
          Last run failed: {latest.error_message}
        </p>
      )}

      {latest && latest.status === "ok" && (
        <>
          <CubeGrid>
            {geoCubes(latest.signals).map((c) => (
              <Cube key={c.label} {...c} />
            ))}
          </CubeGrid>

          {latest.signals.sitemap_scan_truncated && (
            <p className="band-note">
              Sitemap scan stopped after {latest.signals.sitemap_files_read} files
              — the counts above are a lower bound.
            </p>
          )}
        </>
      )}
    </section>
  );
}

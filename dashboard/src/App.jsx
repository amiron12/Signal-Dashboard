import { useEffect, useState } from "react";
import { getCompany, setCompany as saveCompany, scan, getHistory } from "./api.js";
import NewsMentionsCard from "./NewsMentionsCard.jsx";
import SeoOnpageCard from "./SeoOnpageCard.jsx";
import GeoReadinessCard from "./GeoReadinessCard.jsx";
import TrendSection from "./TrendSection.jsx";

// History is fetched here rather than per card: the trend chart switches
// between six metrics across all three receivers without refetching, so one
// load covers everything.
const RECEIVERS = ["seo_onpage", "geo_readiness", "news_mentions"];

// When the wall as a whole last changed. Each card renders its own latest
// event, so this is the newest of those — including a failed run, since a
// card showing "last run failed" was updated by that run too. Null until
// there's anything to report: no runs means no timestamp to state.
function lastUpdatedAt(histories) {
  const latest = Object.values(histories)
    .map((events) => events[events.length - 1])
    .filter(Boolean)
    .map((event) => new Date(event.timestamp));

  return latest.length > 0 ? new Date(Math.max(...latest)) : null;
}

export default function App() {
  const [company, setCompany] = useState(null);
  const [nameInput, setNameInput] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [histories, setHistories] = useState({});
  // Which signal's trend is open, by signal key. null means no chart at all —
  // the selection lives here because the cards raise it and the chart reads it.
  const [activeMetric, setActiveMetric] = useState(null);

  // The open metric's own icon closes the chart; any other icon switches to it.
  function toggleMetric(key) {
    setActiveMetric((current) => (current === key ? null : key));
  }

  useEffect(() => {
    getCompany().then((c) => {
      setCompany(c);
      setNameInput(c.name);
      setUrlInput(c.url);
    });
  }, []);

  useEffect(() => {
    if (!company?.name) return;
    Promise.all(RECEIVERS.map((r) => getHistory(company.name, r))).then((results) =>
      setHistories(Object.fromEntries(RECEIVERS.map((r, i) => [r, results[i]])))
    );
  }, [company?.name, refreshKey]);

  async function handleSaveCompany(e) {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await saveCompany(nameInput, urlInput);
      setCompany(updated);
      // The new company's history arrives a moment later; leaving the chart up
      // would show the old company's line under the new company's name.
      setActiveMetric(null);
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setSaveError(String(err.message ?? err));
    } finally {
      setSaving(false);
    }
  }

  const lastUpdated = lastUpdatedAt(histories);

  async function handleScan() {
    setScanning(true);
    setScanError(null);
    try {
      await scan();
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setScanError(String(e));
    } finally {
      setScanning(false);
    }
  }

  return (
    <div className={`wall ${scanning ? "scanning" : ""}`}>
      <nav className="nav">
        <div className="nav-brand">Signal Wall</div>
        <form className="nav-form" onSubmit={handleSaveCompany}>
          <input
            className="input"
            value={nameInput}
            onChange={(e) => setNameInput(e.target.value)}
            placeholder="Company name"
            style={{ width: 160 }}
          />
          <input
            className="input"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="https://company.com"
          />
          <button type="submit" className="btn btn-secondary" disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </button>
        </form>
        <button className="btn btn-primary" onClick={handleScan} disabled={scanning}>
          {scanning ? "Scanning…" : "Scan now"}
        </button>
      </nav>

      {saveError && <p className="error">{saveError}</p>}
      {scanError && <p className="error">{scanError}</p>}

      {lastUpdated && (
        <div className="last-updated">
          <span className="last-updated-label">Last updated</span>
          <span className="last-updated-value">
            {lastUpdated.toLocaleString(undefined, {
              year: "numeric",
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
              hour12: false,
            })}
          </span>
        </div>
      )}

      <div className="wall-grid">
        <div className="wall-bands">
          <SeoOnpageCard
            history={histories.seo_onpage ?? []}
            activeMetric={activeMetric}
            onToggleMetric={toggleMetric}
          />
          <GeoReadinessCard
            history={histories.geo_readiness ?? []}
            activeMetric={activeMetric}
            onToggleMetric={toggleMetric}
          />
        </div>
        <NewsMentionsCard
          history={histories.news_mentions ?? []}
          activeMetric={activeMetric}
          onToggleMetric={toggleMetric}
        />
      </div>

      <TrendSection histories={histories} activeMetric={activeMetric} />

      {scanning && (
        <div className="scan-overlay">
          <div className="spinner" />
          <p className="scan-overlay-text">Scanning…</p>
        </div>
      )}
    </div>
  );
}

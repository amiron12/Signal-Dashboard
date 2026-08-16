import { useEffect, useState } from "react";
import { getCompany, setCompany as saveCompany, scan, getHistory } from "./api.js";
import NewsMentionsCard from "./NewsMentionsCard.jsx";
import SeoOnpageCard from "./SeoOnpageCard.jsx";
import GeoReadinessCard from "./GeoReadinessCard.jsx";
import TrendSection from "./TrendSection.jsx";

// History is fetched here rather than per card: the trend chart switches
// between all three series without refetching, so one load covers everything.
const RECEIVERS = ["seo_onpage", "geo_readiness", "news_mentions"];

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
      setRefreshKey((k) => k + 1);
    } catch (err) {
      setSaveError(String(err.message ?? err));
    } finally {
      setSaving(false);
    }
  }

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
    <div className="wall">
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

      <div className="wall-grid">
        <div className="wall-bands">
          <SeoOnpageCard history={histories.seo_onpage ?? []} />
          <GeoReadinessCard history={histories.geo_readiness ?? []} />
        </div>
        <NewsMentionsCard history={histories.news_mentions ?? []} />
      </div>

      <TrendSection histories={histories} />
    </div>
  );
}

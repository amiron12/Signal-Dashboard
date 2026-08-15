import { useEffect, useState } from "react";
import { getCompany, setCompany as saveCompany, scan } from "./api.js";
import NewsMentionsCard from "./NewsMentionsCard.jsx";
import SeoOnpageCard from "./SeoOnpageCard.jsx";
import GeoReadinessCard from "./GeoReadinessCard.jsx";

export default function App() {
  const [company, setCompany] = useState(null);
  const [nameInput, setNameInput] = useState("");
  const [urlInput, setUrlInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [scanError, setScanError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    getCompany().then((c) => {
      setCompany(c);
      setNameInput(c.name);
      setUrlInput(c.url);
    });
  }, []);

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
    <div style={{ fontFamily: "sans-serif", maxWidth: 700, margin: "2rem auto" }}>
      <h1>Signal Dashboard</h1>

      <form
        onSubmit={handleSaveCompany}
        style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}
      >
        <input
          value={nameInput}
          onChange={(e) => setNameInput(e.target.value)}
          placeholder="Company name"
        />
        <input
          value={urlInput}
          onChange={(e) => setUrlInput(e.target.value)}
          placeholder="https://company.com"
          style={{ flex: 1 }}
        />
        <button type="submit" disabled={saving}>
          {saving ? "Saving..." : "Save"}
        </button>
      </form>

      {saveError && <p style={{ color: "red" }}>{saveError}</p>}

      <button onClick={handleScan} disabled={scanning} style={{ marginTop: "1rem" }}>
        {scanning ? "Scanning..." : "Scan now"}
      </button>

      {scanError && <p style={{ color: "red" }}>{scanError}</p>}

      <NewsMentionsCard company={company?.name} refreshKey={refreshKey} />
      <SeoOnpageCard company={company?.name} refreshKey={refreshKey} />
      <GeoReadinessCard company={company?.name} refreshKey={refreshKey} />
    </div>
  );
}

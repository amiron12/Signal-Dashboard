import { useEffect, useState } from "react";
import { getCompany, scan } from "./api.js";
import NewsMentionsCard from "./NewsMentionsCard.jsx";
import SeoOnpageCard from "./SeoOnpageCard.jsx";

export default function App() {
  const [company, setCompany] = useState(null);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  useEffect(() => {
    getCompany().then(setCompany);
  }, []);

  async function handleScan() {
    setScanning(true);
    setError(null);
    try {
      await scan();
      setRefreshKey((k) => k + 1);
    } catch (e) {
      setError(String(e));
    } finally {
      setScanning(false);
    }
  }

  return (
    <div style={{ fontFamily: "sans-serif", maxWidth: 700, margin: "2rem auto" }}>
      <h1>Signal Dashboard</h1>

      {company && (
        <p>
          Tracking: <strong>{company.name}</strong> ({company.url})
        </p>
      )}

      <button onClick={handleScan} disabled={scanning}>
        {scanning ? "Scanning..." : "Scan now"}
      </button>

      {error && <p style={{ color: "red" }}>{error}</p>}

      <NewsMentionsCard company={company?.name} refreshKey={refreshKey} />
      <SeoOnpageCard company={company?.name} refreshKey={refreshKey} />
    </div>
  );
}

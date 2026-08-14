const API_BASE = "http://localhost:8000";

export async function getCompany() {
  const res = await fetch(`${API_BASE}/company`);
  return res.json();
}

export async function setCompany(name, url) {
  const res = await fetch(`${API_BASE}/company`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, url }),
  });
  if (!res.ok) {
    const body = await res.json();
    throw new Error(body.detail?.[0]?.msg ?? "Failed to save company");
  }
  return res.json();
}

export async function getHistory(company, receiver) {
  const params = new URLSearchParams({ company, receiver });
  const res = await fetch(`${API_BASE}/history?${params}`);
  return res.json();
}

export async function scan() {
  const res = await fetch(`${API_BASE}/scan`, { method: "POST" });
  return res.json();
}

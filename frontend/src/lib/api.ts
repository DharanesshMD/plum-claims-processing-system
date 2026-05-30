const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function submitClaim(data: unknown) {
  const res = await fetch(`${API_BASE}/api/claims`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function submitClaimStream(data: unknown): Promise<Response> {
  const res = await fetch(`${API_BASE}/api/claims/submit-stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(await res.text());
  return res;
}


export async function listClaims() {
  const res = await fetch(`${API_BASE}/api/claims`, { cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function getClaim(claimId: string) {
  const res = await fetch(`${API_BASE}/api/claims/${claimId}`, { cache: "no-store" });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function runEval() {
  const res = await fetch(`${API_BASE}/api/claims/eval`, {
    method: "POST",
    cache: "no-store",
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

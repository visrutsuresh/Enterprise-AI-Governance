const BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000"; // local default matches #1 and #4; run one app at a time

export async function api(path: string, init: RequestInit = {}) {
  const res = await fetch(`${BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init.headers || {}) },
    ...init,
  });
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.status === 204 ? null : res.json();
}

export const API_BASE = BASE;

export async function upload(path: string, file: File) {
  // deliberately NOT api(): that helper pins Content-Type to application/json,
  // and a multipart body must set its own header so the browser can append the
  // boundary marker. Setting it by hand here would corrupt every upload.
  const body = new FormData();
  body.append("file", file);
  const res = await fetch(`${BASE}${path}`, { method: "POST", credentials: "include", body });
  if (!res.ok) {
    const raw = await res.text();
    let msg = raw;
    try {
      msg = JSON.parse(raw).detail ?? raw;
    } catch {
      // not JSON, the raw text is the best message we have
    }
    throw new Error(msg);
  }
  return res.json();
}

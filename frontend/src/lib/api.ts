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

// The backend writes its 4xx messages for a human to read. api() wraps them as
// `Error: 403: {"detail":"..."}`, and screens were printing that verbatim, so the
// one useful sentence arrived buried in JSON behind a stack-trace prefix.
export function readable(e: unknown): string {
  const raw = e instanceof Error ? e.message : String(e);
  const m = raw.match(/^(\d{3}):\s*([\s\S]*)$/);
  const body = m ? m[2] : raw;
  try {
    const parsed = JSON.parse(body);
    const detail = parsed.detail ?? parsed.message;
    if (typeof detail === "string") return detail;
    // FastAPI validation errors arrive as a list of {loc, msg}
    if (Array.isArray(detail)) {
      return detail.map((d) => `${(d.loc ?? []).slice(-1)[0] ?? ""}: ${d.msg}`.trim()).join("; ");
    }
  } catch {
    // not JSON: the text itself is the best message we have
  }
  if (m?.[1] === "429") return "Too many requests. Wait a moment and try again.";
  if (m?.[1] === "401") return "Your session has expired. Sign in again.";
  return body || "Something went wrong.";
}

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

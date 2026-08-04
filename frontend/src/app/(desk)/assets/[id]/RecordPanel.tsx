"use client";
import { useState } from "react";
import { api } from "@/lib/api";

// the fields a reviewer may correct. Mirrors EDITABLE_FIELDS in app/schemas.py:
// the server is the one that enforces it, this list only decides what is drawn.
type Field = {
  key: string;
  label: string;
  kind: "text" | "select" | "area" | "tags" | "date";
  options?: string[];
  scoring?: boolean;
};

const FIELDS: Field[] = [
  { key: "name", label: "name", kind: "text" },
  { key: "type", label: "type", kind: "select", options: ["model", "agent"], scoring: true },
  { key: "owner", label: "owner", kind: "text" },
  { key: "lifecycle", label: "lifecycle", kind: "select", options: ["proposed", "development", "production", "retired"], scoring: true },
  { key: "business_unit", label: "business unit", kind: "text" },
  { key: "region", label: "region", kind: "text" },
  { key: "purpose", label: "purpose", kind: "area" },
  { key: "deployment", label: "deployment", kind: "text", scoring: true },
  { key: "data_touched", label: "data touched", kind: "tags", scoring: true },
  { key: "third_party", label: "third party", kind: "text", scoring: true },
  { key: "human_oversight", label: "human oversight", kind: "text", scoring: true },
  { key: "protected_attributes", label: "protected attributes", kind: "tags" },
  { key: "last_bias_test_at", label: "last bias test", kind: "date" },
];

export default function RecordPanel({
  assetId,
  asset,
  fieldSource,
  onSaved,
}: {
  assetId: string;
  asset: Record<string, unknown>;
  fieldSource: Record<string, { was: unknown; by: string; at: string }>;
  onSaved: (msg: string) => void;
}) {
  const [editing, setEditing] = useState("");
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  function open(f: Field) {
    const v = asset[f.key];
    setDraft(Array.isArray(v) ? v.join(", ") : String(v ?? ""));
    setEditing(f.key);
    setErr("");
  }

  async function save(f: Field) {
    setBusy(true);
    setErr("");
    // a tag field is typed as one comma-separated line: a chip editor is a lot
    // of machinery for a list that is three items long
    const value =
      f.kind === "tags" ? draft.split(",").map((s) => s.trim()).filter(Boolean) : draft.trim();
    try {
      const r = await api(`/assets/${assetId}`, {
        method: "PATCH",
        body: JSON.stringify({ fields: { [f.key]: value } }),
      });
      setEditing("");
      onSaved(
        r.rescore?.changed
          ? `Saved and re-scored: ${r.rescore.added.length} finding(s) added, ${r.rescore.removed.length} no longer apply.`
          : "Saved to the record."
      );
    } catch (e) {
      // a 409 means it is already that value, which is not worth a scary message
      const msg = String(e);
      setErr(msg.includes("409") ? "That is already what the record says." : msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel p-5 space-y-4">
      <div>
        <h2 className="text-[16px] font-bold" style={{ fontFamily: "var(--font-cabinet)" }}>
          The record
        </h2>
        <p className="text-[12.5px] text-[var(--ink-soft)] mt-1 max-w-[62ch]">
          Written by the inventory agent from one paragraph of prose. Click any value to correct it.
          A field marked with a dot feeds the rules, so correcting it re-scores the asset with no
          model call and no cost.
        </p>
      </div>

      {err && <p className="text-[12.5px] text-[#e5484d]">{err}</p>}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6 gap-y-4">
        {FIELDS.map((f) => {
          const src = fieldSource?.[f.key];
          const raw = asset[f.key];
          const shown = Array.isArray(raw) ? raw.join(", ") : (raw as string | null);
          return (
            <div key={f.key}>
              <div className="text-[11px] uppercase tracking-wide text-[var(--ink-soft)] flex items-center gap-1.5">
                {f.label}
                <span
                  title={src ? `corrected by ${src.by}` : "as the inventory agent wrote it"}
                  className="inline-block w-[6px] h-[6px] rounded-full"
                  style={{ background: src ? "var(--accent)" : "var(--ink-soft)" }}
                />
                {f.scoring && (
                  <span
                    className="text-[8px] text-[var(--ink-soft)]"
                    title="changing this re-scores the asset"
                  >
                    &#9679;
                  </span>
                )}
              </div>

              {editing === f.key ? (
                <div className="flex items-center gap-2 mt-1">
                  {f.kind === "select" ? (
                    <select
                      autoFocus
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      className="field text-[13px] flex-1"
                    >
                      {f.options!.map((o) => (
                        <option key={o}>{o}</option>
                      ))}
                    </select>
                  ) : (
                    <input
                      autoFocus
                      type={f.kind === "date" ? "date" : "text"}
                      value={draft}
                      onChange={(e) => setDraft(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") save(f);
                        if (e.key === "Escape") setEditing("");
                      }}
                      className="field text-[13px] flex-1"
                    />
                  )}
                  <button className="btn" disabled={busy} onClick={() => save(f)}>
                    Save
                  </button>
                  <button
                    className="text-[12px] text-[var(--ink-soft)] underline underline-offset-4"
                    onClick={() => setEditing("")}
                  >
                    cancel
                  </button>
                </div>
              ) : (
                <div
                  onClick={() => open(f)}
                  className="text-[13.5px] mt-0.5 px-2 py-1 -mx-2 rounded cursor-text hover:bg-white/[0.03]"
                >
                  {shown || <span className="text-[var(--ink-soft)] italic">not stated</span>}
                </div>
              )}

              {src && (
                <div className="text-[10px] font-array text-[var(--accent)] tracking-wider mt-0.5">
                  EDITED &middot; WAS {JSON.stringify(src.was)}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

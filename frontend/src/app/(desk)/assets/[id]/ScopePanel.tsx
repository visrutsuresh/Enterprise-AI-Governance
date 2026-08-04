"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

type Control = {
  id: string;
  title: string;
  requirement: string;
  framework: string;
  tier: string;
  attested: { status: string; note: string; by: string; at: string } | null;
};

const STATUS_COLOR: Record<string, string> = {
  met: "var(--olive)",
  not_met: "var(--rust)",
  not_applicable: "var(--ink-soft)",
};

export default function ScopePanel({
  assetId,
  packs,
  onSaved,
}: {
  assetId: string;
  packs: { policy?: string; framework?: string; extra_frameworks?: string[] };
  onSaved: (msg: string) => void;
}) {
  const [avail, setAvail] = useState<{ policy_packs: string[]; framework_packs: string[] } | null>(null);
  const [controls, setControls] = useState<Control[]>([]);
  const [policy, setPolicy] = useState(packs.policy ?? "");
  const [framework, setFramework] = useState(packs.framework ?? "");
  const [extra, setExtra] = useState<string[]>(packs.extra_frameworks ?? []);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [noteFor, setNoteFor] = useState("");
  const [note, setNote] = useState("");

  const loadControls = useCallback(() => {
    api(`/assets/${assetId}/controls`)
      .then((r) => setControls(r.controls))
      .catch((e) => setErr(String(e)));
  }, [assetId]);

  useEffect(() => {
    api("/packs/available")
      .then((a) => {
        setAvail(a);
        // an asset that never chose falls through to the env default, and the
        // server told us what that is, so seed the selects from it
        if (!policy) setPolicy(a.policy_packs[0] ?? "");
        if (!framework) setFramework(a.framework_packs[0] ?? "");
      })
      .catch(() => {});
    loadControls();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadControls]);

  async function applyScope() {
    if (!reason.trim()) {
      setErr("Say why this scope applies.");
      return;
    }
    setBusy(true);
    setErr("");
    try {
      const r = await api(`/assets/${assetId}/packs`, {
        method: "PUT",
        body: JSON.stringify({ policy, framework, extra_frameworks: extra, reason }),
      });
      setReason("");
      loadControls();
      onSaved(
        `Re-scored under ${r.packs.policy}: ${r.rescore.added.length} added, ${r.rescore.removed.length} no longer apply.`
      );
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  async function attest(c: Control, status: string) {
    // a control that is not met has to say what is missing, so ask before sending
    if (status !== "met" && !note.trim()) {
      setNoteFor(c.id);
      return;
    }
    setBusy(true);
    setErr("");
    try {
      await api(`/assets/${assetId}/controls/${c.id}`, {
        method: "PUT",
        body: JSON.stringify({ status, note }),
      });
      setNoteFor("");
      setNote("");
      loadControls();
      onSaved(`${c.id} marked ${status.replace("_", " ")}.`);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="panel p-5 space-y-5">
      <div>
        <h2 className="text-[16px] font-bold" style={{ fontFamily: "var(--font-cabinet)" }}>
          Which rules bind this asset
        </h2>
        <p className="text-[12.5px] text-[var(--ink-soft)] mt-1 max-w-[62ch]">
          One estate, many rulebooks. A credit model serving EU customers and an internal document
          sorter are not under the same law, so the choice sits here rather than in one setting for
          the whole register.
        </p>
      </div>

      {err && <p className="text-[12.5px] text-[#e5484d]">{err}</p>}

      <div className="flex flex-wrap gap-5 items-start">
        <label className="text-[12.5px]">
          <div className="text-[11px] uppercase tracking-wide text-[var(--ink-soft)] mb-1">
            company policy
          </div>
          <select value={policy} onChange={(e) => setPolicy(e.target.value)} className="field text-[13px]">
            {(avail?.policy_packs ?? []).map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>

        <label className="text-[12.5px]">
          <div className="text-[11px] uppercase tracking-wide text-[var(--ink-soft)] mb-1">
            primary regulation
          </div>
          <select value={framework} onChange={(e) => setFramework(e.target.value)} className="field text-[13px]">
            {(avail?.framework_packs ?? []).map((p) => (
              <option key={p}>{p}</option>
            ))}
          </select>
        </label>

        <div className="text-[12.5px]">
          <div className="text-[11px] uppercase tracking-wide text-[var(--ink-soft)] mb-1">
            also assessed under
          </div>
          {(avail?.framework_packs ?? []).filter((p) => p !== framework).length === 0 && (
            <span className="text-[var(--ink-soft)]">nothing else on disk yet</span>
          )}
          {(avail?.framework_packs ?? [])
            .filter((p) => p !== framework)
            .map((p) => (
              <label key={p} className="flex items-center gap-2 py-0.5">
                <input
                  type="checkbox"
                  checked={extra.includes(p)}
                  onChange={(e) =>
                    setExtra(e.target.checked ? [...extra, p] : extra.filter((x) => x !== p))
                  }
                  style={{ accentColor: "var(--accent)" }}
                />
                {p}
              </label>
            ))}
        </div>

        <div className="flex-1 min-w-[220px]">
          <div className="text-[11px] uppercase tracking-wide text-[var(--ink-soft)] mb-1">
            why this scope
          </div>
          <input
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. EU customers, so the Act applies"
            className="field text-[13px] w-full"
          />
          <button className="btn mt-2" disabled={busy} onClick={applyScope}>
            Apply and re-score
          </button>
        </div>
      </div>

      <div className="pt-4 border-t border-[var(--line)]">
        <h3 className="text-[14px] font-semibold">Controls at this tier</h3>
        <p className="text-[12.5px] text-[var(--ink-soft)] mt-1 max-w-[62ch]">
          These are written as prose, so no code can honestly decide whether they are met. A person
          says, and signs, and it joins the audit chain.
        </p>

        <div className="mt-3">
          {controls.length === 0 && (
            <p className="text-[12.5px] text-[var(--ink-soft)]">
              No controls to show: this asset has no tier yet, so nothing has been narrowed down to.
            </p>
          )}
          {controls.map((c) => (
            <div
              key={`${c.framework}-${c.id}`}
              className="flex flex-wrap items-center gap-3 py-2 border-b border-[var(--line)] last:border-0"
            >
              <span
                className="font-array text-[10px] tracking-wider w-[86px]"
                style={{ color: STATUS_COLOR[c.attested?.status ?? ""] ?? "var(--ink-soft)" }}
              >
                {(c.attested?.status ?? "unanswered").replace("_", " ").toUpperCase()}
              </span>
              <span className="text-[12px] font-mono w-[76px] text-[var(--ink-soft)]">{c.id}</span>
              <span className="text-[13px] flex-1 min-w-[200px]" title={c.requirement}>
                {c.title}
              </span>
              <span className="flex gap-2">
                {["met", "not_met", "not_applicable"].map((s) => (
                  <button
                    key={s}
                    className="btn ghost text-[11px]"
                    disabled={busy}
                    onClick={() => attest(c, s)}
                  >
                    {s.replace("_", " ")}
                  </button>
                ))}
              </span>
              {noteFor === c.id && (
                <span className="flex gap-2 w-full mt-1">
                  <input
                    autoFocus
                    value={note}
                    onChange={(e) => setNote(e.target.value)}
                    placeholder="what is missing?"
                    className="field text-[12.5px] flex-1"
                  />
                  <button className="btn" onClick={() => attest(c, "not_met")}>
                    Save
                  </button>
                </span>
              )}
              {c.attested?.note && (
                <span className="w-full text-[11.5px] text-[var(--ink-soft)]">
                  {c.attested.note} &mdash; {c.attested.by}
                </span>
              )}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

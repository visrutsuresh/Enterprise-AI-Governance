"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, API_BASE } from "@/lib/api";
import { STAGES, TIER_COLORS } from "@/lib/stages";

type Finding = {
  finding_id: string;
  inspector: string;
  control_id: string;
  severity: string;
  plain: string;
  evidence: string;
  remediation: string;
  status: string;
  routed_to?: string;
  review?: { verdict: string; reason: string; by: string; at: string };
};

type AuditView = {
  entries: { step: string; hash: string }[];
  count: number;
  intact: boolean;
  broken_at: number | null;
};

const SEV_COLOR: Record<string, string> = { high: "#c95a4a", medium: "#a0772d", low: "#5f9a5c" };

export default function AssetDetail() {
  const { id } = useParams<{ id: string }>();
  const [state, setState] = useState<Record<string, any> | null>(null);
  const [audit, setAudit] = useState<AuditView | null>(null);
  const [showAudit, setShowAudit] = useState(false);
  const [busy, setBusy] = useState("");
  const [overriding, setOverriding] = useState(""); // finding id whose override reason is being typed
  const [reason, setReason] = useState("");
  const [actError, setActError] = useState(""); // a failed click must say so, not silently no-op
  const [pollFailed, setPollFailed] = useState(false);
  const [tierEdit, setTierEdit] = useState(false);
  type EvidenceRow = { id: number; filename: string; size: number; uploaded_by: string };
  const [files, setFiles] = useState<Record<string, EvidenceRow[]>>({}); // evidence per finding, fetched on demand
  const [newTier, setNewTier] = useState("high");
  const [tierReason, setTierReason] = useState("");

  const refresh = useCallback(() => {
    api(`/assets/${id}`)
      .then((s) => {
        setState(s);
        setPollFailed(false);
      })
      .catch(() => setPollFailed(true));
  }, [id]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [refresh]);

  async function loadAudit() {
    setShowAudit(true);
    try {
      setAudit(await api(`/assets/${id}/audit`));
    } catch (e) {
      setActError(`Could not load the audit trail: ${e}`);
    }
  }

  async function route(finding_id: string) {
    setBusy(finding_id);
    setActError("");
    try {
      await api(`/flags/${finding_id}/route`, { method: "POST" });
      refresh();
      if (showAudit) loadAudit();
    } catch (e) {
      setActError(`Routing did not go through: ${e}`);
    } finally {
      setBusy("");
    }
  }

  // the reviewer's verdict on a flag. an override must carry a reason, which is
  // the whole point: a dismissal with no reason is what an auditor objects to.
  async function decide(finding_id: string, verdict: "approved" | "overridden") {
    setBusy(finding_id);
    setActError("");
    try {
      await api(`/flags/${finding_id}/decision`, {
        method: "POST",
        body: JSON.stringify({ verdict, reason }),
      });
      setOverriding("");
      setReason("");
      refresh();
      if (showAudit) loadAudit();
    } catch (e) {
      setActError(`That decision did not go through: ${e}`);
    } finally {
      setBusy("");
    }
  }

  // the human correction path for the headline judgement itself (the model
  // mis-tiers ~1 in 4); the correction lands on the audit chain server-side
  async function overrideTier() {
    setBusy("tier");
    setActError("");
    try {
      await api(`/assets/${id}/tier`, {
        method: "POST",
        body: JSON.stringify({ tier: newTier, reason: tierReason }),
      });
      setTierEdit(false);
      setTierReason("");
      refresh();
      if (showAudit) loadAudit();
    } catch (e) {
      setActError(`Tier override did not go through: ${e}`);
    } finally {
      setBusy("");
    }
  }

  async function loadFiles(finding_id: string) {
    try {
      const r = await api(`/flags/${finding_id}/evidence`);
      setFiles((p) => ({ ...p, [finding_id]: r }));
    } catch (e) {
      setActError(`Could not load evidence: ${e}`);
    }
  }

  if (!state) return <main className="py-10 text-[var(--ink-soft)]">Loading...</main>;

  const asset = state.asset || {};
  const assessment = asset.assessment || {};
  const findings: Finding[] = assessment.findings || [];
  const checks: Record<string, string> = assessment.inspector_status || {};
  const tier = (state.risk_tier || assessment.risk_tier || "").toLowerCase();

  const fact = (label: string, value: React.ReactNode) => (
    <div>
      <div className="text-[11.5px] uppercase tracking-wide text-[var(--ink-soft)]">{label}</div>
      <div className="text-[13.5px]">{value || <span className="text-[var(--ink-soft)]">not stated</span>}</div>
    </div>
  );

  return (
    <main className="py-8 space-y-6">
      <Link href="/tower" className="text-[13px] underline underline-offset-4">
        &larr; Control tower
      </Link>

      {pollFailed && (
        <p className="text-[12.5px] text-[#e5484d]">
          Connection trouble: showing the last known state, retrying every few seconds.
        </p>
      )}
      {actError && <p className="text-[12.5px] text-[#e5484d]">{actError}</p>}

      <div className="flex items-center gap-4">
        <h1 className="text-[26px] font-extrabold" style={{ fontFamily: "var(--font-cabinet)" }}>
          {asset.name || state.asset_id}
        </h1>
        {tier && (
          <span
            className="px-2.5 py-1 rounded-full text-white text-[12px] font-semibold"
            style={{ background: TIER_COLORS[tier] || "#525252" }}
          >
            {tier} risk
          </span>
        )}
        {tier && !tierEdit && (
          <button
            className="text-[12px] underline underline-offset-4 text-[var(--ink-soft)]"
            onClick={() => setTierEdit(true)}
          >
            correct tier
          </button>
        )}
        {tierEdit && (
          <span className="flex items-center gap-2">
            <select
              value={newTier}
              onChange={(e) => setNewTier(e.target.value)}
              className="text-[12.5px] bg-transparent border border-[var(--line)] rounded px-2 py-1"
            >
              {["unacceptable", "high", "limited", "minimal"].map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
            <input
              value={tierReason}
              onChange={(e) => setTierReason(e.target.value)}
              placeholder="why the assigned tier is wrong"
              className="text-[12.5px] bg-transparent border border-[var(--line)] rounded px-2 py-1 w-64"
            />
            <button className="btn" disabled={busy !== "" || !tierReason.trim()} onClick={overrideTier}>
              Save
            </button>
            <button
              className="text-[12px] underline underline-offset-4 text-[var(--ink-soft)]"
              onClick={() => setTierEdit(false)}
            >
              cancel
            </button>
          </span>
        )}
        {state.tier_override && !tierEdit && (
          <span className="text-[11.5px] text-[var(--ink-soft)]">
            corrected from {state.tier_override.from} by {state.tier_override.by}
          </span>
        )}
        <span
          className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase ${
            asset.source === "seed" ? "bg-[var(--line)] text-[var(--ink-soft)]" : "bg-[var(--accent)] text-[#1c2126]"
          }`}
        >
          {asset.source}
        </span>
        {state.status === "processing" && (
          <span className="text-[var(--accent)] animate-pulse text-[14px]">
            {STAGES[state.stage] || state.stage}...
          </span>
        )}
      </div>

      {state.status === "error" && (
        <div className="border border-[var(--rust)] bg-[var(--rust-wash)] rounded-xl p-4 text-[13.5px]">{state.error}</div>
      )}

      <section className="border border-[var(--line)] rounded-xl p-5 bg-[var(--paper)] grid grid-cols-2 md:grid-cols-4 gap-4">
        {fact("asset id", asset.asset_id)}
        {fact("type", asset.type)}
        {fact("owner", asset.owner)}
        {fact("lifecycle", asset.lifecycle)}
        {fact("purpose", asset.purpose)}
        {fact("deployment", asset.deployment)}
        {fact("data touched", (asset.data_touched || []).join(", "))}
        {fact("third party", asset.third_party)}
        {fact("human oversight", asset.human_oversight)}
        {fact("decision", assessment.decision)}
        {fact("risk score", assessment.risk ? `${assessment.risk.score}/100 (${assessment.risk.why})` : "")}
        {fact(
          "inspectors",
          Object.entries(checks)
            .map(([k, v]) => `${k.replaceAll("_", " ")}: ${v}`)
            .join(" | ")
        )}
      </section>

      <section className="space-y-3">
        <h2 className="text-[17px] font-bold" style={{ fontFamily: "var(--font-cabinet)" }}>
          Findings ({findings.length})
        </h2>
        {findings.length === 0 && (
          <div className="text-[13.5px] text-[var(--ink-soft)]">
            {state.status === "processing" ? "Assessment still running." : "No findings: compliant."}
          </div>
        )}
        {findings.map((f) => (
          <div key={f.finding_id} className="border border-[var(--line)] rounded-xl p-4 bg-[var(--paper)] space-y-1.5">
            <div className="flex items-center gap-3">
              <span
                className="px-2 py-0.5 rounded-full text-white text-[11px] font-semibold"
                style={{ background: SEV_COLOR[f.severity] || "#525252" }}
              >
                {f.severity}
              </span>
              <span className="text-[12.5px] font-mono">{f.control_id}</span>
              <span className="text-[12px] text-[var(--ink-soft)]">by {f.inspector.replaceAll("_", " ")}</span>
              <span className="ml-auto text-[12px] text-[var(--ink-soft)]">{f.finding_id}</span>
            </div>
            <div className="text-[14.5px] font-medium">{f.plain}</div>
            <div className="text-[12.5px] text-[var(--ink-soft)]">Evidence: {f.evidence}</div>
            <div className="text-[12.5px]">Fix: {f.remediation}</div>
            <div className="text-[12.5px]">
              <button
                className="underline underline-offset-4 text-[var(--ink-soft)]"
                onClick={() => loadFiles(f.finding_id)}
              >
                {files[f.finding_id] ? "refresh attached evidence" : "show attached evidence"}
              </button>
              {files[f.finding_id] &&
                (files[f.finding_id].length === 0 ? (
                  <span className="ml-2 text-[var(--ink-soft)]">none attached yet (uploads live on the remediation board)</span>
                ) : (
                  <ul className="mt-1 space-y-0.5">
                    {files[f.finding_id].map((ev) => (
                      <li key={ev.id}>
                        <a href={`${API_BASE}/evidence/${ev.id}`} className="underline underline-offset-4">
                          {ev.filename}
                        </a>{" "}
                        <span className="text-[var(--ink-soft)]">
                          ({Math.max(1, Math.round(ev.size / 1024))} KB, by {ev.uploaded_by})
                        </span>
                      </li>
                    ))}
                  </ul>
                ))}
            </div>
            <div className="flex items-center gap-3 pt-1 flex-wrap">
              {f.routed_to ? (
                <span className="text-[12.5px]">
                  Routed to <b>{f.routed_to}</b>
                </span>
              ) : (
                <button className="btn" disabled={busy !== ""} onClick={() => route(f.finding_id)}>
                  {busy === f.finding_id ? "Routing..." : "Route to a team"}
                </button>
              )}

              {f.review ? (
                <span className="text-[12.5px]">
                  <b>{f.review.verdict === "approved" ? "Confirmed" : "Overridden"}</b> by {f.review.by}
                  {f.review.reason && <span className="text-[var(--ink-soft)]"> &mdash; {f.review.reason}</span>}
                </span>
              ) : (
                <>
                  <button className="btn" disabled={busy !== ""} onClick={() => decide(f.finding_id, "approved")}>
                    {busy === f.finding_id ? "Saving..." : "Approve"}
                  </button>
                  <button
                    className="btn"
                    disabled={busy !== ""}
                    onClick={() => {
                      setOverriding(f.finding_id);
                      setReason("");
                    }}
                  >
                    Override
                  </button>
                </>
              )}
            </div>

            {overriding === f.finding_id && !f.review && (
              <div className="flex items-center gap-2 pt-1">
                <input
                  autoFocus
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Why does this not apply? (recorded in the audit trail)"
                  className="flex-1 border border-[var(--line)] rounded px-2 py-1 text-[13px] bg-transparent"
                />
                <button
                  className="btn"
                  disabled={!reason.trim() || busy !== ""}
                  onClick={() => decide(f.finding_id, "overridden")}
                >
                  Save override
                </button>
                <button
                  className="text-[12.5px] underline underline-offset-4 text-[var(--ink-soft)]"
                  onClick={() => {
                    setOverriding("");
                    setReason("");
                  }}
                >
                  cancel
                </button>
              </div>
            )}
          </div>
        ))}
      </section>

      <section className="border border-[var(--line)] rounded-xl p-5 bg-[var(--paper)] space-y-3">
        <div className="flex items-center gap-4">
          <h2 className="text-[17px] font-bold" style={{ fontFamily: "var(--font-cabinet)" }}>
            Audit trail
          </h2>
          {!showAudit && (
            <button className="btn" onClick={loadAudit}>
              Open the trail
            </button>
          )}
          {audit && (
            <span
              className={`px-2 py-0.5 rounded text-[12px] font-semibold text-white ${
                audit.intact ? "bg-[#5f9a5c]" : "bg-[#c95a4a]"
              }`}
            >
              {audit.intact ? "chain intact" : `TAMPERED at entry ${audit.broken_at}`}
            </span>
          )}
        </div>
        {audit && (
          <ol className="space-y-1">
            {audit.entries.map((e, i) => (
              <li
                key={i}
                className={`text-[12.5px] font-mono px-2 py-1 rounded ${
                  audit.broken_at !== null && i >= (audit.broken_at as number)
                    ? "bg-[var(--rust-wash)] text-[var(--rust)]"
                    : ""
                }`}
              >
                {i}. {e.step}
                <span className="text-[var(--ink-soft)]"> [{e.hash.slice(0, 10)}...]</span>
              </li>
            ))}
            {audit.count === 0 && (
              <li className="text-[12.5px] text-[var(--ink-soft)]">
                Empty chain: this is a seeded fixture, no pipeline ever ran on it.
              </li>
            )}
          </ol>
        )}
      </section>
    </main>
  );
}

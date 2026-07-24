"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
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
};

type AuditView = {
  entries: { step: string; hash: string }[];
  count: number;
  intact: boolean;
  broken_at: number | null;
};

const SEV_COLOR: Record<string, string> = { high: "#b91c1c", medium: "#b45309", low: "#15803d" };

export default function AssetDetail() {
  const { id } = useParams<{ id: string }>();
  const [state, setState] = useState<Record<string, any> | null>(null);
  const [audit, setAudit] = useState<AuditView | null>(null);
  const [showAudit, setShowAudit] = useState(false);
  const [busy, setBusy] = useState("");

  const refresh = useCallback(() => {
    api(`/assets/${id}`).then(setState).catch(() => {});
  }, [id]);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [refresh]);

  async function loadAudit() {
    setShowAudit(true);
    setAudit(await api(`/assets/${id}/audit`));
  }

  async function route(finding_id: string) {
    setBusy(finding_id);
    try {
      await api(`/flags/${finding_id}/route`, { method: "POST" });
      refresh();
      if (showAudit) loadAudit();
    } finally {
      setBusy("");
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
        <span
          className={`px-2 py-0.5 rounded text-[11px] font-semibold uppercase ${
            asset.source === "seed" ? "bg-[var(--line)] text-[var(--ink-soft)]" : "bg-[var(--accent)] text-white"
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
        <div className="border border-red-300 bg-red-50 rounded-xl p-4 text-[13.5px]">{state.error}</div>
      )}

      <section className="border border-[var(--line)] rounded-xl p-5 bg-white/60 grid grid-cols-2 md:grid-cols-4 gap-4">
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
          <div key={f.finding_id} className="border border-[var(--line)] rounded-xl p-4 bg-white/60 space-y-1.5">
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
            <div className="flex items-center gap-3 pt-1">
              {f.routed_to ? (
                <span className="text-[12.5px]">
                  Routed to <b>{f.routed_to}</b>
                </span>
              ) : (
                <button className="btn" disabled={busy !== ""} onClick={() => route(f.finding_id)}>
                  {busy === f.finding_id ? "Routing..." : "Route to a team"}
                </button>
              )}
            </div>
          </div>
        ))}
      </section>

      <section className="border border-[var(--line)] rounded-xl p-5 bg-white/60 space-y-3">
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
                audit.intact ? "bg-[#15803d]" : "bg-[#b91c1c]"
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
                    ? "bg-red-50 text-red-800"
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

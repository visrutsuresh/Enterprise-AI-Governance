"use client";
import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { API_BASE, api, readable } from "@/lib/api";
import { STAGES, sevClass, tierClass } from "@/lib/stages";
import RecordPanel from "./RecordPanel";
import ScopePanel from "./ScopePanel";
import MeasurementPanel from "./MeasurementPanel";
import EffectRail from "./EffectRail";

/* THE COCKPIT (layout C).
   Section rail on the left, one section at a time in the middle, and on the
   right a column that never leaves: what the record adds up to. The page used
   to be one long scroll of everything at once, which is fine at four panels and
   unreadable at seven. */

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

type EvidenceRow = { id: number; filename: string; size: number; uploaded_by: string };

// the stored GovernanceState, as much of it as this page reads
type AssetState = {
  asset_id: string;
  status: string;
  stage: string;
  error?: string | null;
  risk_tier?: string | null;
  decision?: string;
  fairness_metric?: string;
  field_source?: Record<string, { was: unknown; by: string; at: string }>;
  packs?: { policy?: string; framework?: string; extra_frameworks?: string[] };
  audit?: { step: string }[];
  asset?: Record<string, unknown> & {
    name?: string;
    source?: string;
    assessment?: { risk_tier?: string; decision?: string; findings?: Finding[] };
  };
};

const SECTIONS = [
  { key: "record", label: "Record" },
  { key: "scope", label: "Rulebooks" },
  { key: "measure", label: "Measurement" },
  { key: "findings", label: "Findings" },
  { key: "audit", label: "Audit" },
] as const;


export default function AssetDetail() {
  const { id } = useParams<{ id: string }>();
  const [state, setState] = useState<AssetState | null>(null);
  const [section, setSection] = useState<string>("record");
  const [notice, setNotice] = useState("");
  const [pollFailed, setPollFailed] = useState(false);
  const [actError, setActError] = useState("");
  const [audit, setAudit] = useState<{
    entries: { step: string; hash: string }[];
    count: number;
    intact: boolean;
    broken_at: number | null;
  } | null>(null);
  const [metric, setMetric] = useState<{ short: string; value: number; pass: boolean } | null>(null);
  const [busy, setBusy] = useState("");
  const [overriding, setOverriding] = useState("");
  const [reason, setReason] = useState("");
  const [files, setFiles] = useState<Record<string, EvidenceRow[]>>({});
  const [tierEdit, setTierEdit] = useState(false);
  const [newTier, setNewTier] = useState("high");
  const [tierReason, setTierReason] = useState("");
  const [logging, setLogging] = useState(false);
  const [logPlain, setLogPlain] = useState("");
  const [logSeverity, setLogSeverity] = useState("medium");
  const [logEvidence, setLogEvidence] = useState("");

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
    // keep the 4s poll: a running assessment narrates through it, and the rail
    // has to reflect anything a colleague changed in another tab
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [refresh]);

  // the rail wants the bound metric's value, and only the measurement endpoint knows it
  useEffect(() => {
    api(`/assets/${id}/measurements`)
      .then((r) => {
        const last = r.periods[r.periods.length - 1];
        if (!last) return setMetric(null);
        const m = r.metrics_catalogue[r.metric];
        const v = last.computed.fairness[r.metric];
        setMetric({
          short: m.short,
          value: v,
          pass: m.better === "high" ? v >= m.threshold : v <= m.threshold,
        });
      })
      .catch(() => setMetric(null));
  }, [id, state?.decision, state?.fairness_metric]);

  const loadAudit = useCallback(() => {
    api(`/assets/${id}/audit`)
      .then(setAudit)
      .catch((e) => setActError(`Could not load the audit trail: ${e}`));
  }, [id]);

  useEffect(() => {
    if (section === "audit") loadAudit();
  }, [section, loadAudit, state?.audit?.length]);

  function saved(msg: string) {
    setNotice(msg);
    setActError("");
    refresh();
  }

  async function route(finding_id: string) {
    setBusy(finding_id);
    setActError("");
    try {
      await api(`/flags/${finding_id}/route`, { method: "POST" });
      refresh();
    } catch (e) {
      setActError(`Routing did not go through: ${e}`);
    } finally {
      setBusy("");
    }
  }

  async function logIssue() {
    if (!logPlain.trim()) return;
    setBusy("log");
    setActError("");
    try {
      await api(`/assets/${id}/findings`, {
        method: "POST",
        body: JSON.stringify({
          plain: logPlain.trim(),
          severity: logSeverity,
          evidence: logEvidence.trim(),
        }),
      });
      setLogPlain("");
      setLogEvidence("");
      setLogSeverity("medium");
      setLogging(false);
      refresh();
    } catch (e) {
      setActError(readable(e));
    } finally {
      setBusy("");
    }
  }

  async function decide(finding_id: string, verdict: "approved" | "overridden") {
    // `reason` is one box shared by the whole page. Only send it to the finding
    // whose override box is actually open, or an abandoned draft on finding A
    // gets written into finding B's audit entry as its justification.
    const justification = overriding === finding_id ? reason : "";
    if (verdict === "overridden" && !justification.trim()) {
      setActError("An override needs a reason: that reason is what the auditor reads.");
      return;
    }
    setBusy(finding_id);
    setActError("");
    try {
      await api(`/flags/${finding_id}/decision`, {
        method: "POST",
        body: JSON.stringify({ verdict, reason: justification }),
      });
      setOverriding("");
      setReason("");
      refresh();
    } catch (e) {
      setActError(`That decision did not go through: ${e}`);
    } finally {
      setBusy("");
    }
  }

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

  const asset = state.asset ?? {};
  const assessment = asset.assessment ?? {};
  const findings: Finding[] = assessment.findings ?? [];
  const tier = String(state.risk_tier || assessment.risk_tier || "").toLowerCase();

  return (
    <main className="py-6">
      <Link href="/tower" className="text-[13px] underline underline-offset-4">
        &larr; Control tower
      </Link>

      <div className="flex items-center gap-4 flex-wrap mt-4">
        <h1 className="text-[30px] font-extrabold" style={{ fontFamily: "var(--font-cabinet)" }}>
          {asset.name || state.asset_id}
        </h1>
        {tier && (
          <span className={tierClass(tier)}>{tier} risk</span>
        )}
        {tier && !tierEdit && (
          <button
            className="text-[13px] underline underline-offset-4 text-[var(--ink-soft)]"
            onClick={() => setTierEdit(true)}
          >
            correct tier
          </button>
        )}
        {tierEdit && (
          <span className="flex items-center gap-2 flex-wrap">
            <select value={newTier} onChange={(e) => setNewTier(e.target.value)} className="field text-[13px]">
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
              className="field text-[13px] w-64"
            />
            <button className="btn" disabled={busy !== "" || !tierReason.trim()} onClick={overrideTier}>
              Save
            </button>
            <button
              className="text-[13px] underline underline-offset-4 text-[var(--ink-soft)]"
              onClick={() => setTierEdit(false)}
            >
              cancel
            </button>
          </span>
        )}
        <span
          className={`px-2 py-0.5 rounded text-[13px] font-semibold uppercase ${
            asset.source === "pipeline" ? "bg-[var(--accent)] text-white" : "bg-[var(--line)] text-[var(--ink-soft)]"
          }`}
        >
          {asset.source}
        </span>
        {state.status === "processing" && (
          <span className="text-[var(--accent)] animate-pulse text-[13px]">
            {STAGES[state.stage] || state.stage}...
          </span>
        )}
      </div>

      {pollFailed && (
        <p className="text-[13px] text-[var(--danger)] mt-2">
          Connection trouble: showing the last known state, retrying every few seconds.
        </p>
      )}
      {state.status === "error" && (
        <div
          className="mt-3 rounded-[3px] p-4 text-[13px]"
          style={{ background: "var(--rust-wash)", color: "var(--rust)" }}
        >
          {state.error}
        </div>
      )}
      {actError && <p className="text-[13px] text-[var(--danger)] mt-2">{actError}</p>}
      {notice && <p className="text-[13px] text-[var(--accent)] mt-2">{notice}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-[200px_minmax(0,1fr)_360px] gap-10 mt-6 items-start">
        <nav className="lg:sticky lg:top-5 flex lg:flex-col gap-1 flex-wrap">
          {SECTIONS.map((s) => (
            <button
              key={s.key}
              onClick={() => setSection(s.key)}
              className={`text-left font-array text-[13px] tracking-[0.12em] uppercase px-3 py-2 rounded-[3px] transition-colors ${
                section === s.key
                  ? "text-[var(--ink)] bg-[var(--accent-wash)]"
                  : "text-[var(--ink-soft)] hover:text-[var(--ink)]"
              }`}
            >
              {s.label}
              {s.key === "findings" && findings.length > 0 && (
                <span className="text-[var(--accent)] ml-1.5">{findings.length}</span>
              )}
            </button>
          ))}
        </nav>

        <div>
          {section === "record" && (
            <RecordPanel
              assetId={id}
              asset={asset}
              fieldSource={state.field_source ?? {}}
              onSaved={saved}
            />
          )}

          {section === "scope" && (
            <ScopePanel assetId={id} packs={state.packs ?? {}} onSaved={saved} />
          )}

          {section === "measure" && <MeasurementPanel assetId={id} onSaved={saved} />}

          {section === "findings" && (
            <section className="panel p-7 space-y-3">
              <div className="flex items-center gap-3">
                <h2 className="text-[17px] font-bold" style={{ fontFamily: "var(--font-cabinet)" }}>
                  Findings ({findings.length})
                </h2>
                <button className="btn ghost ml-auto" onClick={() => setLogging(!logging)}>
                  {logging ? "Cancel" : "Log an issue"}
                </button>
              </div>

              {/* every finding here used to come from an agent. An issue found in a
                  pen test, an incident or a meeting simply could not be written down. */}
              {logging && (
                <div className="border border-[var(--line)] rounded-[3px] p-3 space-y-2">
                  <p className="text-[13px] text-[var(--ink-soft)]">
                    Something you already know is wrong. It joins the audit chain as raised by you,
                    and lands on the remediation board like any other finding.
                  </p>
                  <input
                    autoFocus
                    value={logPlain}
                    onChange={(e) => setLogPlain(e.target.value)}
                    placeholder="What is wrong, in one sentence"
                    className="field w-full text-[13px]"
                  />
                  <div className="flex gap-2 flex-wrap items-center">
                    <select
                      value={logSeverity}
                      onChange={(e) => setLogSeverity(e.target.value)}
                      className="field text-[13px]"
                    >
                      {["high", "medium", "low"].map((s) => (
                        <option key={s} value={s}>{s} severity</option>
                      ))}
                    </select>
                    <input
                      value={logEvidence}
                      onChange={(e) => setLogEvidence(e.target.value)}
                      placeholder="How do you know? (report, ticket, date)"
                      className="field text-[13px] flex-1 min-w-[200px]"
                    />
                  </div>
                  <button className="btn" disabled={busy !== "" || !logPlain.trim()} onClick={logIssue}>
                    {busy === "log" ? "Saving..." : "Log it"}
                  </button>
                </div>
              )}
              {findings.length === 0 && (
                <p className="text-[13px] text-[var(--ink-soft)]">
                  {state.status === "processing" ? "Assessment still running." : "No findings: compliant."}
                </p>
              )}
              {findings.map((f) => (
                <div key={f.finding_id} className="border-t border-[var(--line)] pt-3 first:border-t-0">
                  <div className="flex items-center gap-3 flex-wrap">
                    <span className={sevClass(f.severity)}>{f.severity}</span>
                    <span className="text-[13px] font-mono">{f.control_id}</span>
                    <span className="text-[13px] text-[var(--ink-soft)]">
                      by {f.inspector.replaceAll("_", " ")}
                    </span>
                    <span className="ml-auto text-[13px] text-[var(--ink-soft)]">{f.finding_id}</span>
                  </div>
                  <div className="text-[13px] font-medium mt-1.5">{f.plain}</div>
                  <div className="text-[13px] text-[var(--ink-soft)] mt-0.5">Evidence: {f.evidence}</div>
                  <div className="text-[13px]">Fix: {f.remediation}</div>

                  <div className="text-[13px] mt-1">
                    <button
                      className="underline underline-offset-4 text-[var(--ink-soft)]"
                      onClick={() => loadFiles(f.finding_id)}
                    >
                      {files[f.finding_id] ? "refresh attached evidence" : "show attached evidence"}
                    </button>
                    {files[f.finding_id] &&
                      (files[f.finding_id].length === 0 ? (
                        <span className="ml-2 text-[var(--ink-soft)]">
                          none attached yet (uploads live on the remediation board)
                        </span>
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

                  <div className="flex items-center gap-3 pt-2 flex-wrap">
                    {f.routed_to ? (
                      <span className="text-[13px]">
                        Routed to <b>{f.routed_to}</b>
                      </span>
                    ) : (
                      <button className="btn ghost" disabled={busy !== ""} onClick={() => route(f.finding_id)}>
                        {busy === f.finding_id ? "Routing..." : "Route to a team"}
                      </button>
                    )}

                    {f.review ? (
                      <span className="text-[13px]">
                        <b>{f.review.verdict === "approved" ? "Confirmed" : "Overridden"}</b> by {f.review.by}
                        {f.review.reason && (
                          <span className="text-[var(--ink-soft)]"> &mdash; {f.review.reason}</span>
                        )}
                      </span>
                    ) : (
                      <>
                        <button
                          className="btn ghost"
                          disabled={busy !== ""}
                          onClick={() => decide(f.finding_id, "approved")}
                        >
                          Approve
                        </button>
                        <button
                          className="btn ghost"
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
                    <div className="flex items-center gap-2 pt-2">
                      <input
                        autoFocus
                        value={reason}
                        onChange={(e) => setReason(e.target.value)}
                        placeholder="Why does this not apply? (recorded in the audit trail)"
                        className="field flex-1 text-[13px]"
                      />
                      <button
                        className="btn"
                        disabled={!reason.trim() || busy !== ""}
                        onClick={() => decide(f.finding_id, "overridden")}
                      >
                        Save override
                      </button>
                      <button
                        className="text-[13px] underline underline-offset-4 text-[var(--ink-soft)]"
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
          )}

          {section === "audit" && (
            <section className="panel p-7 space-y-3">
              <div className="flex items-center gap-3">
                <h2 className="text-[17px] font-bold" style={{ fontFamily: "var(--font-cabinet)" }}>
                  Audit trail
                </h2>
                {audit && (
                  // intact was green and tampered was red, the only saturated pair
                  // left in the app. Tampered is now the heaviest chip on the page,
                  // which is what the app's central claim deserves.
                  <span className={`sev ${audit.intact ? "sev-mid" : "sev-hi"}`}>
                    {audit.intact ? "chain intact" : `TAMPERED at entry ${audit.broken_at}`}
                  </span>
                )}
              </div>
              <ol className="space-y-1">
                {(audit?.entries ?? []).map((e, i) => (
                  <li
                    key={i}
                    className={`text-[13px] font-mono px-2 py-1 rounded ${
                      audit?.broken_at !== null && audit?.broken_at !== undefined && i >= audit.broken_at
                        ? "bg-[var(--rust-wash)] text-[var(--rust)]"
                        : ""
                    }`}
                  >
                    {i}. {e.step} <span className="text-[var(--ink-soft)]">[{e.hash.slice(0, 10)}...]</span>
                  </li>
                ))}
                {audit?.count === 0 && (
                  <li className="text-[13px] text-[var(--ink-soft)]">
                    Empty chain: this is a seeded fixture, no pipeline ever ran on it.
                  </li>
                )}
              </ol>
            </section>
          )}
        </div>

        <EffectRail state={state} metric={metric} />
      </div>
    </main>
  );
}

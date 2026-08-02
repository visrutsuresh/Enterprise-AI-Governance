"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api";
import { STAGES, TIER_COLORS } from "@/lib/stages";
import { useUser } from "@/lib/useUser";

type Row = {
  asset_id: string;
  name: string | null;
  type: string | null;
  owner: string | null;
  lifecycle: string | null;
  status: string;
  stage: string;
  risk_level: string | null;
  risk_tier: string | null;
  source: string | null;
  open_findings: number;
};

type Packs = {
  policy_pack: { id: string; name: string; rules: number };
  framework_pack: { id: string; name: string; tiers: number };
};

type Metric = { value: number | string; detail?: string; sample?: boolean; unit?: string };
type Metrics = Record<string, Record<string, Metric>>;

const METRIC_GROUPS: { key: string; title: string; metrics: { key: string; label: string }[] }[] = [
  {
    key: "portfolio",
    title: "AI Portfolio",
    metrics: [
      { key: "total_use_cases", label: "Total AI Use Cases" },
      { key: "in_production", label: "AI Applications in Production" },
      { key: "under_review", label: "AI Projects Under Review" },
      { key: "adoption_rate", label: "AI Adoption Rate" },
    ],
  },
  {
    key: "risk",
    title: "Risk",
    metrics: [
      { key: "high_risk_systems", label: "High-Risk AI Systems" },
      { key: "open_issues", label: "Open Governance Issues" },
      { key: "policy_violations", label: "Policy Violations" },
      { key: "third_party_risks", label: "Third-Party AI Risks" },
    ],
  },
  {
    key: "compliance",
    title: "Compliance",
    metrics: [
      { key: "compliance_score", label: "Compliance Score" },
      { key: "regulatory_readiness", label: "Regulatory Readiness" },
      { key: "audit_findings", label: "Audit Findings" },
      { key: "approval_status", label: "Approval Status" },
    ],
  },
  {
    key: "responsible_ai",
    title: "Responsible AI",
    metrics: [
      { key: "bias_assessment", label: "Bias Assessment Status" },
      { key: "explainability_coverage", label: "Explainability Coverage" },
      { key: "human_oversight", label: "Human Oversight Compliance" },
      { key: "model_transparency", label: "Model Transparency Score" },
    ],
  },
  {
    key: "operational",
    title: "Operational",
    metrics: [
      { key: "model_performance", label: "Model Performance" },
      { key: "model_drift_incidents", label: "Model Drift Incidents" },
      { key: "security_findings", label: "Security Findings" },
      { key: "sla_compliance", label: "Governance SLA Compliance" },
    ],
  },
];

function MetricTile({ label, m }: { label: string; m: Metric | undefined }) {
  if (!m) return null;
  const shown = m.unit ? `${m.value}${m.unit}` : m.value;
  return (
    <div className="relative border border-[var(--line)] rounded-xl px-5 py-4 bg-[var(--paper)]">
      {m.sample && (
        <span
          title="labelled sample: no real estate signal for this metric yet, shown as an illustrative placeholder"
          className="absolute top-2 right-2 px-1.5 py-0.5 rounded text-[9.5px] font-semibold uppercase tracking-wide bg-[var(--line)] text-[var(--ink-soft)]"
        >
          sample
        </span>
      )}
      <div className="text-[12px] uppercase tracking-wide text-[var(--ink-soft)] pr-12">{label}</div>
      <div className="text-[26px] font-extrabold" style={{ fontFamily: "var(--font-cabinet)" }}>
        {shown}
      </div>
      {m.detail && <div className="text-[11px] text-[var(--ink-soft)] mt-1 leading-snug">{m.detail}</div>}
    </div>
  );
}

function TierChip({ tier }: { tier: string | null }) {
  if (!tier) return <span className="text-[var(--ink-soft)]">-</span>;
  return (
    <span
      className="px-2 py-0.5 rounded-full text-white text-[11.5px] font-semibold"
      style={{ background: TIER_COLORS[tier] || "#525252" }}
    >
      {tier}
    </span>
  );
}

function SourceBadge({ source }: { source: string | null }) {
  const seed = source === "seed";
  return (
    <span
      title={seed ? "authored fixture, no pipeline ran" : "real pipeline output"}
      className={`px-1.5 py-0.5 rounded text-[10.5px] font-semibold uppercase tracking-wide ${
        seed
          ? "bg-[var(--line)] text-[var(--ink-soft)]"
          : "bg-[var(--accent)] text-[#1c2126]"
      }`}
    >
      {source || "?"}
    </span>
  );
}

export default function Tower() {
  const { user } = useUser();
  const [rows, setRows] = useState<Row[]>([]);
  const [packs, setPacks] = useState<Packs | null>(null);
  const [description, setDescription] = useState("");
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [brief, setBrief] = useState("");
  const [report, setReport] = useState("");
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [pollFailed, setPollFailed] = useState(false);
  const alive = useRef(true); // the sweep poll loop must die with the page
  useEffect(() => {
    alive.current = true;
    // reattach: a reload mid-sweep should still learn the outcome
    api("/sweep/status")
      .then((s) => {
        if (s.state === "running") setNotice("A sweep is running server-side; its report will appear when it finishes.");
        if (s.state === "done" && s.report) setReport(s.report.report);
      })
      .catch(() => {});
    return () => {
      alive.current = false;
    };
  }, []);
  const [q, setQ] = useState("");
  const [tierFilter, setTierFilter] = useState("");
  const [flaggedOnly, setFlaggedOnly] = useState("");

  // 185 assets filter instantly client-side; no server round-trip needed
  const needle = q.trim().toLowerCase();
  const shown = rows.filter(
    (r) =>
      (!needle ||
        `${r.name} ${r.asset_id} ${r.owner ?? ""} ${r.type ?? ""}`.toLowerCase().includes(needle)) &&
      (!tierFilter || r.risk_tier === tierFilter) &&
      (!flaggedOnly || (r.open_findings || 0) > 0)
  );

  const refresh = useCallback(() => {
    // the estate poll is the page's pulse: a dead backend must show a banner,
    // not silently freeze the screen on stale numbers
    api("/assets")
      .then((r) => {
        setRows(r);
        setPollFailed(false);
      })
      .catch(() => setPollFailed(true));
    api("/packs").then(setPacks).catch(() => {});
    api("/metrics").then(setMetrics).catch(() => {});
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 4000);
    return () => clearInterval(t);
  }, [refresh]);

  async function register() {
    if (!description.trim()) return;
    setBusy("register");
    try {
      await api("/assets", { method: "POST", body: JSON.stringify({ description }) });
      setDescription("");
      setNotice("Registered. The assessment narrates below as it runs.");
      refresh();
    } catch (e) {
      setNotice(String(e));
    } finally {
      setBusy("");
    }
  }

  async function swapPack(framework_pack: string | null, policy_pack: string | null) {
    setBusy("swap");
    setNotice("");
    try {
      const r = await api("/packs/activate", {
        method: "POST",
        body: JSON.stringify({ framework_pack, policy_pack }),
      });
      setNotice(
        `Pack swapped to ${r.rescore.pack}: ${r.rescore.assets_rescored} assets re-scored, zero code changed.`
      );
      refresh();
    } catch (e) {
      setNotice(String(e));
    } finally {
      setBusy("");
    }
  }

  async function runSweep() {
    setBusy("sweep");
    setNotice("Sweep started in the background (each asset is a model call, expect minutes)...");
    try {
      await api("/sweep/run", { method: "POST", body: JSON.stringify({ limit: 10 }) });
      // the run happens server-side now; poll until it lands instead of holding one request open
      for (let i = 0; i < 120 && alive.current; i++) {
        await new Promise((res) => setTimeout(res, 5000));
        if (!alive.current) return;
        const s = await api("/sweep/status");
        if (s.state === "done") {
          const r = s.report;
          setReport(r.report);
          setNotice(
            `Sweep done: ${r.monitored} monitored, ${r.new_findings} new finding(s), ${r.not_swept} not swept tonight.`
          );
          refresh();
          return;
        }
        if (s.state === "error") {
          setNotice(`Sweep failed: ${s.error}`);
          return;
        }
      }
      setNotice("Sweep is still running server-side; it will finish without this page.");
    } catch (e) {
      setNotice(String(e));
    } finally {
      setBusy("");
    }
  }

  async function fetchBrief() {
    setBusy("brief");
    try {
      const r = await api("/brief");
      setBrief(r.brief);
    } catch (e) {
      setNotice(String(e));
    } finally {
      setBusy("");
    }
  }

  const tiers: Record<string, number> = {};
  let flagged = 0;
  for (const r of rows) {
    if (r.risk_tier) tiers[r.risk_tier] = (tiers[r.risk_tier] || 0) + 1;
    if (r.open_findings > 0) flagged += 1;
  }

  const stat = (label: string, value: React.ReactNode) => (
    <div className="border border-[var(--line)] rounded-xl px-5 py-4 bg-[var(--paper)]">
      <div className="text-[12px] uppercase tracking-wide text-[var(--ink-soft)]">{label}</div>
      <div className="text-[26px] font-extrabold" style={{ fontFamily: "var(--font-cabinet)" }}>
        {value}
      </div>
    </div>
  );

  return (
    <main className="py-8 space-y-6">
      {pollFailed && (
        <p className="text-[12.5px] text-[#e5484d]">
          Connection trouble: showing the last known estate, retrying every few seconds.
        </p>
      )}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        {stat("assets", rows.length)}
        {stat("with open flags", flagged)}
        {stat("unacceptable", tiers["unacceptable"] || 0)}
        {stat("high", tiers["high"] || 0)}
        {stat("limited", tiers["limited"] || 0)}
        {stat("minimal", tiers["minimal"] || 0)}
      </div>

      {metrics && (
        <div className="space-y-5">
          <h2 className="text-[17px] font-bold" style={{ fontFamily: "var(--font-cabinet)" }}>
            Executive dashboard
          </h2>
          {METRIC_GROUPS.map((g) => (
            <section key={g.key} className="space-y-2">
              <div className="text-[13px] font-semibold text-[var(--ink-soft)] uppercase tracking-wide">
                {g.title}
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                {g.metrics.map((m) => (
                  <MetricTile key={m.key} label={m.label} m={metrics[g.key]?.[m.key]} />
                ))}
              </div>
            </section>
          ))}
        </div>
      )}

      <section className="border border-[var(--line)] rounded-xl p-5 bg-[var(--paper)] space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="text-[14px] font-semibold">Live packs:</div>
          {packs && (
            <>
              <span className="text-[13px] px-2 py-1 rounded bg-[var(--line)]">
                policy {packs.policy_pack.id} ({packs.policy_pack.rules} rules)
              </span>
              <span className="text-[13px] px-2 py-1 rounded bg-[var(--line)]">
                framework {packs.framework_pack.id} ({packs.framework_pack.tiers} tiers)
              </span>
            </>
          )}
          {user?.role === "admin" && (
            <div className="ml-auto flex gap-2">
              <button
                className="btn"
                disabled={busy !== ""}
                onClick={() =>
                  swapPack(null, packs?.policy_pack.id.startsWith("acme") ? "globex" : "acme")
                }
              >
                Swap policy pack
              </button>
              <button className="btn" disabled={busy !== ""} onClick={runSweep}>
                Run nightly sweep
              </button>
            </div>
          )}
          <button className="btn" disabled={busy !== ""} onClick={fetchBrief}>
            Executive brief
          </button>
        </div>
        {notice && <div className="text-[13px] text-[var(--accent)]">{notice}</div>}
        {brief && <p className="text-[13.5px] whitespace-pre-wrap border-t border-[var(--line)] pt-3">{brief}</p>}
        {report && (
          <p className="text-[13.5px] whitespace-pre-wrap border-t border-[var(--line)] pt-3">
            <b>Overnight report:</b> {report}
          </p>
        )}
      </section>

      <section className="border border-[var(--line)] rounded-xl p-5 bg-[var(--paper)] space-y-2">
        <div className="text-[14px] font-semibold">Register an AI system</div>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          placeholder="Describe it in plain words: what it does, who owns it, what data it reads, where it runs, who checks its output..."
          className="w-full border border-[var(--line)] rounded-lg p-3 text-[13.5px] bg-[var(--parchment)]"
        />
        <button className="btn" disabled={busy !== "" || !description.trim()} onClick={register}>
          {busy === "register" ? "Registering..." : "Register and assess"}
        </button>
      </section>

      <div className="flex items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search the register (name, id, owner, type)"
          className="flex-1 text-[13px] bg-transparent border border-[var(--line)] rounded-lg px-3 py-2 outline-none placeholder:text-[var(--ink-soft)]"
        />
        <select
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value)}
          className="text-[12.5px] bg-transparent border border-[var(--line)] rounded-lg px-2 py-2"
        >
          <option value="">all tiers</option>
          {["unacceptable", "high", "limited", "minimal"].map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select
          value={flaggedOnly}
          onChange={(e) => setFlaggedOnly(e.target.value)}
          className="text-[12.5px] bg-transparent border border-[var(--line)] rounded-lg px-2 py-2"
        >
          <option value="">all assets</option>
          <option value="flagged">open flags only</option>
        </select>
        {(q || tierFilter || flaggedOnly) && (
          <span className="text-[12px] text-[var(--ink-soft)]">
            {shown.length} of {rows.length}
          </span>
        )}
      </div>

      <table className="w-full text-[13.5px]">
        <thead>
          <tr className="text-left text-[12px] uppercase tracking-wide text-[var(--ink-soft)] border-b border-[var(--line)]">
            <th className="py-2 pr-3">Asset</th>
            <th className="py-2 pr-3">Type</th>
            <th className="py-2 pr-3">Lifecycle</th>
            <th className="py-2 pr-3">Tier</th>
            <th className="py-2 pr-3">Open flags</th>
            <th className="py-2 pr-3">Provenance</th>
            <th className="py-2 pr-3">Status</th>
          </tr>
        </thead>
        <tbody>
          {shown.length === 0 && (
            <tr>
              <td colSpan={7} className="py-4 text-[var(--ink-soft)]">
                No assets match. Clear the search or filters to see the full register.
              </td>
            </tr>
          )}
          {shown.map((r) => (
            <tr key={r.asset_id} className="border-b border-[var(--line)] hover:bg-white/5">
              <td className="py-2.5 pr-3">
                <Link href={`/assets/${r.asset_id}`} className="font-medium hover:text-[var(--accent)]">
                  {r.name || r.asset_id}
                </Link>
                <span className="ml-2 text-[11.5px] text-[var(--ink-soft)]">{r.asset_id}</span>
              </td>
              <td className="py-2.5 pr-3">{r.type || "-"}</td>
              <td className="py-2.5 pr-3">{r.lifecycle || "-"}</td>
              <td className="py-2.5 pr-3">
                <TierChip tier={r.risk_tier} />
              </td>
              <td className="py-2.5 pr-3">{r.open_findings || 0}</td>
              <td className="py-2.5 pr-3">
                <SourceBadge source={r.source} />
              </td>
              <td className="py-2.5 pr-3">
                {r.status === "processing" ? (
                  <span className="text-[var(--accent)] animate-pulse">
                    {STAGES[r.stage] || r.stage}...
                  </span>
                ) : (
                  r.status
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}

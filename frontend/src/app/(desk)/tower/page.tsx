"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api, readable } from "@/lib/api";
import { STAGES, tierClass } from "@/lib/stages";
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

type Metric = {
  value: number | string;
  detail?: string;
  unit?: string;
  tone?: "flat" | "higher_better" | "lower_better";
  good?: number; // at or past this, the number is healthy
  bad?: number; // at or past this, it needs attention
};
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
      { key: "audit_findings", label: "Audit Findings" },
      { key: "approval_status", label: "Awaiting a Decision" },
    ],
  },
  {
    key: "responsible_ai",
    title: "Responsible AI",
    metrics: [
      { key: "bias_assessment", label: "Open Bias Findings" },
      { key: "human_oversight", label: "Human Oversight Compliance" },
    ],
  },
  {
    key: "operational",
    title: "Operational",
    metrics: [
      { key: "model_drift_incidents", label: "Model Drift Incidents" },
      { key: "dismissed_findings", label: "Dismissed, With a Reason" },
    ],
  },
];

// Is this number good news or bad? A dashboard of undifferentiated digits makes
// the reader do the judging, which is the one job a governance dashboard has.
// The verdict is carried by WEIGHT and by a word, never by hue: a tile that
// needs attention is the heaviest thing in its row.
type Verdict = { word: string; rank: 0 | 1 | 2 };
function verdictOf(m: Metric): Verdict | null {
  if (!m.tone || m.tone === "flat" || typeof m.value !== "number") return null;
  if (m.good === undefined || m.bad === undefined) return null;
  const healthy = m.tone === "higher_better" ? m.value >= m.good : m.value <= m.good;
  const poor = m.tone === "higher_better" ? m.value <= m.bad : m.value >= m.bad;
  if (healthy) return { word: "healthy", rank: 0 };
  if (poor) return { word: "needs attention", rank: 2 };
  return { word: "watch", rank: 1 };
}

function MetricTile({ label, m }: { label: string; m: Metric | undefined }) {
  // a metric the backend did not report must say so, not quietly leave a gap in
  // the row that reads as "we looked and there was nothing"
  if (!m) {
    return (
      <div className="border border-dashed border-[var(--line)] rounded-[3px] px-5 py-4">
        <div className="label">{label}</div>
        <div className="text-[13px] text-[var(--ink-dim)] mt-2">not reported</div>
      </div>
    );
  }
  const shown = m.unit ? `${m.value}${m.unit}` : m.value;
  const v = verdictOf(m);
  const alarm = v?.rank === 2;
  return (
    <div
      className={`relative rounded-[3px] px-5 py-4 transition-colors ${
        alarm ? "border-2 border-[var(--ink)] bg-[var(--wash)]" : "border border-[var(--line)]"
      }`}
    >
      <div className="label">{label}</div>
      <div
        className={`text-[30px] leading-none mt-2 ${alarm ? "font-extrabold" : "font-semibold"}`}
        style={{ fontFamily: "var(--font-cabinet)" }}
      >
        {shown}
      </div>
      {v && (
        // the word is the meaning. It reads on a projector, in greyscale, and
        // for anyone who cannot separate red from green.
        <div
          className={`mt-1.5 text-[13px] uppercase tracking-[0.14em] font-bold ${
            v.rank === 2 ? "text-[var(--ink)]" : v.rank === 1 ? "text-[var(--ink-soft)]" : "text-[var(--ink-dim)]"
          }`}
        >
          {v.word}
        </div>
      )}
      {m.detail && <div className="text-[13px] text-[var(--ink-soft)] mt-2 leading-snug">{m.detail}</div>}
    </div>
  );
}

const EMPTY_REG = {
  name: "", owner: "", purpose: "", type: "model", lifecycle: "development",
  deployment: "", third_party: "", data_touched: "", human_oversight: "",
  business_unit: "", region: "", protected_attributes: "",
};

// the dot marks a field the policy rules actually read. Getting one of these
// wrong is not cosmetic: the rule silently does not fire and the asset scores clean.
function Label({ label, required, scoring }: { label: string; required?: boolean; scoring?: boolean }) {
  return (
    <span className="text-[13px] uppercase tracking-wide text-[var(--ink-soft)]">
      {label}
      {required && <span className="text-[var(--rust)]"> *</span>}
      {scoring && <span className="text-[var(--accent)]" title="feeds the risk rules"> &bull;</span>}
    </span>
  );
}

function Field({ label, value, onChange, placeholder, required, scoring }: {
  label: string; value: string; onChange: (v: string) => void;
  placeholder?: string; required?: boolean; scoring?: boolean;
}) {
  return (
    <label className="block">
      <Label label={label} required={required} scoring={scoring} />
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="field w-full mt-1 text-[13px]"
      />
    </label>
  );
}

function Choice({ label, value, options, onChange, scoring }: {
  label: string; value: string; options: string[];
  onChange: (v: string) => void; scoring?: boolean;
}) {
  return (
    <label className="block">
      <Label label={label} scoring={scoring} />
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="field w-full mt-1 text-[13px]"
      >
        {options.map((o) => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>
    </label>
  );
}

function TierChip({ tier }: { tier: string | null }) {
  if (!tier) return <span className="text-[var(--ink-soft)]">-</span>;
  return (
    <span className={tierClass(tier)}>{tier}</span>
  );
}

function SourceBadge({ source }: { source: string | null }) {
  const seed = source === "seed";
  return (
    <span
      title={seed ? "authored fixture, no pipeline ran" : "real pipeline output"}
      className={`px-1.5 py-0.5 rounded-[3px] text-[13px] font-semibold uppercase tracking-wide ${
        seed
          ? "bg-[var(--line)] text-[var(--ink-soft)]"
          : "bg-[var(--accent)] text-white"
      }`}
    >
      {source || "?"}
    </span>
  );
}

export default function Tower() {
  const { user } = useUser();
  const router = useRouter();
  const [loaded, setLoaded] = useState(false); // "nothing registered" must not show while loading
  const [regMode, setRegMode] = useState<"form" | "prose">("form");
  const [regOpen, setRegOpen] = useState(false);
  const [reg, setReg] = useState(EMPTY_REG);
  const [rows, setRows] = useState<Row[]>([]);
  const [packs, setPacks] = useState<Packs | null>(null);
  const [avail, setAvail] = useState<{ policy_packs: string[]; framework_packs: string[] } | null>(null);
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
        setLoaded(true);
        setPollFailed(false);
      })
      .catch(() => {
        setLoaded(true);
        setPollFailed(true);
      });
    api("/packs").then(setPacks).catch(() => {});
    api("/packs/available").then(setAvail).catch(() => {});
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

  async function registerManual() {
    setBusy("manual");
    setNotice("");
    try {
      const list = (s: string) =>
        s.split(",").map((x) => x.trim()).filter(Boolean);
      const r = await api("/assets/manual", {
        method: "POST",
        body: JSON.stringify({
          ...reg,
          data_touched: list(reg.data_touched),
          protected_attributes: list(reg.protected_attributes),
          third_party: reg.third_party.trim() || null,
        }),
      });
      setReg(EMPTY_REG);
      setNotice(`Registered ${r.asset_id} and scored against the policy pack. No model call.`);
      refresh();
    } catch (e) {
      setNotice(readable(e));
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
      if (r.active) setPacks(r.active);
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
    <div className="border border-[var(--line)] rounded-[3px] px-5 py-4 bg-[var(--paper)]">
      <div className="text-[13px] uppercase tracking-wide text-[var(--ink-soft)]">{label}</div>
      <div className="text-[30px] font-extrabold" style={{ fontFamily: "var(--font-cabinet)" }}>
        {value}
      </div>
    </div>
  );

  return (
    <main className="py-8 space-y-6">
      {/* collapsed by default. Registering is an occasional act, and expanded it
          pushed the estate, the thing a reviewer actually looks at daily, below
          the fold. The form-vs-prose switch lives inside it. */}
      <section className="border border-[var(--line)] rounded-[3px] bg-[var(--paper)]">
        <button
          onClick={() => setRegOpen(!regOpen)}
          aria-expanded={regOpen}
          className="w-full flex items-center gap-3 px-5 py-4 text-left hover:bg-[var(--wash)] transition-colors"
        >
          <span className="text-[14px] font-semibold">Register an AI system</span>
          {!regOpen && (
            <span className="text-[13px] text-[var(--ink-soft)]">
              fill a form, or describe it in a sentence
            </span>
          )}
          <span className="ml-auto text-[18px] text-[var(--ink-soft)]" aria-hidden>
            {regOpen ? "−" : "+"}
          </span>
        </button>
        {regOpen && (
          <div className="px-5 pb-5 pt-4 space-y-3 border-t border-[var(--line)]">
            <div className="flex items-center gap-4">
              <div className="text-[13px] font-semibold">Register an AI system</div>
              <div className="flex gap-1 ml-auto">
                {(["form", "prose"] as const).map((m) => (
                  <button
                    key={m}
                    onClick={() => setRegMode(m)}
                    className={`text-[13px] px-3 py-1 rounded-[3px] border transition-colors ${
                      regMode === m
                        ? "border-[var(--ink)] bg-[var(--ink)] text-white"
                        : "border-[var(--line)] text-[var(--ink-soft)] hover:border-[var(--ink)]"
                    }`}
                  >
                    {m === "form" ? "Fill a form" : "Describe it"}
                  </button>
                ))}
              </div>
            </div>

            {regMode === "prose" ? (
              <>
                <p className="text-[13px] text-[var(--ink-soft)]">
                  An agent reads the paragraph and fills the record, then the full assessment runs.
                  Costs a model call, and you correct whatever it got wrong afterwards.
                </p>
                <textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  rows={3}
                  placeholder="Describe it in plain words: what it does, who owns it, what data it reads, where it runs, who checks its output..."
                  className="field w-full text-[13px]"
                />
                <button className="btn" disabled={busy !== "" || !description.trim()} onClick={register}>
                  {busy === "register" ? "Registering..." : "Register and assess"}
                </button>
              </>
            ) : (
              <>
                <p className="text-[13px] text-[var(--ink-soft)]">
                  You already know the answers, so type them. No model call and no cost: the policy
                  rules score it the moment you save. Fields marked with a dot decide which rules fire.
                </p>
                <div className="grid grid-cols-2 gap-3">
                  <Field label="Name" required value={reg.name} onChange={(v) => setReg({ ...reg, name: v })} />
                  <Field label="Owner" required value={reg.owner} onChange={(v) => setReg({ ...reg, owner: v })}
                         placeholder="a person and their team" />
                  <Choice label="Type" scoring value={reg.type} options={["model", "agent"]}
                          onChange={(v) => setReg({ ...reg, type: v })} />
                  <Choice label="Lifecycle" scoring value={reg.lifecycle}
                          options={["proposed", "development", "production", "retired"]}
                          onChange={(v) => setReg({ ...reg, lifecycle: v })} />
                  <div className="col-span-2">
                    <Field label="Purpose" required value={reg.purpose}
                           onChange={(v) => setReg({ ...reg, purpose: v })}
                           placeholder="what decision does it make, and about whom" />
                  </div>
                  <Field label="Deployment" scoring value={reg.deployment}
                         onChange={(v) => setReg({ ...reg, deployment: v })}
                         placeholder="where it runs, e.g. vendor SaaS, on-prem" />
                  <Field label="Third party" scoring value={reg.third_party}
                         onChange={(v) => setReg({ ...reg, third_party: v })}
                         placeholder="vendor name, or leave blank if in-house" />
                  <Field label="Data touched" scoring value={reg.data_touched}
                         onChange={(v) => setReg({ ...reg, data_touched: v })}
                         placeholder="comma separated, e.g. customer PII, health" />
                  <Field label="Human oversight" scoring value={reg.human_oversight}
                         onChange={(v) => setReg({ ...reg, human_oversight: v })}
                         placeholder="who checks it, or blank if nobody" />
                  <Field label="Business unit" value={reg.business_unit}
                         onChange={(v) => setReg({ ...reg, business_unit: v })} />
                  <Field label="Region" value={reg.region} onChange={(v) => setReg({ ...reg, region: v })}
                         placeholder="e.g. EU, SG" />
                  <Field label="Protected attributes" value={reg.protected_attributes}
                         onChange={(v) => setReg({ ...reg, protected_attributes: v })}
                         placeholder="comma separated, e.g. age, gender" />
                </div>
                <button
                  className="btn"
                  disabled={busy !== "" || !reg.name.trim() || !reg.owner.trim() || !reg.purpose.trim()}
                  onClick={registerManual}
                >
                  {busy === "manual" ? "Saving..." : "Register and score"}
                </button>
              </>
            )}
          </div>
        )}
      </section>
      {pollFailed && (
        <p className="text-[13px] text-[var(--danger)]">
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

      <section className="border border-[var(--line)] rounded-[3px] p-5 bg-[var(--paper)] space-y-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="text-[13px] font-semibold">Live packs:</div>
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
            <div className="ml-auto flex items-center gap-2">
              <label className="text-[13px] text-[var(--ink-soft)]">policy</label>
              <select
                className="field text-[13px]"
                disabled={busy !== ""}
                value={avail?.policy_packs.find((s) => packs?.policy_pack.id.startsWith(s)) ?? ""}
                onChange={(e) => swapPack(null, e.target.value)}
              >
                {(avail?.policy_packs ?? []).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
              <label className="text-[13px] text-[var(--ink-soft)]">framework</label>
              <select
                className="field text-[13px]"
                disabled={busy !== ""}
                value={avail?.framework_packs.find((s) => packs?.framework_pack.id.startsWith(s)) ?? ""}
                onChange={(e) => swapPack(e.target.value, null)}
              >
                {(avail?.framework_packs ?? []).map((s) => (
                  <option key={s} value={s}>{s}</option>
                ))}
              </select>
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
        {brief && <p className="text-[13px] whitespace-pre-wrap border-t border-[var(--line)] pt-3">{brief}</p>}
        {report && (
          <p className="text-[13px] whitespace-pre-wrap border-t border-[var(--line)] pt-3">
            <b>Overnight report:</b> {report}
          </p>
        )}
      </section>


      <div className="flex items-center gap-2">
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search the register (name, id, owner, type)"
          className="field flex-1 text-[13px]"
        />
        <select
          value={tierFilter}
          onChange={(e) => setTierFilter(e.target.value)}
          className="field text-[13px]"
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
          className="field text-[13px]"
        >
          <option value="">all assets</option>
          <option value="flagged">open flags only</option>
        </select>
        {(q || tierFilter || flaggedOnly) && (
          <span className="text-[13px] text-[var(--ink-soft)]">
            {shown.length} of {rows.length}
          </span>
        )}
      </div>

      <table className="w-full text-[13px]">
        <thead>
          <tr className="text-left text-[13px] uppercase tracking-wide text-[var(--ink-soft)] border-b border-[var(--line)]">
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
                {/* on a fresh estate the register is empty because nothing has been
                    registered yet, so do not blame a filter nobody set */}
                {!loaded
                  ? "Loading the register..."
                  : rows.length === 0
                    ? "No AI systems registered yet. Register the first one above and the assessment runs straight away."
                    : "No assets match. Clear the search or filters to see the full register."}
              </td>
            </tr>
          )}
          {/* the whole row navigates. It always highlighted on hover, but only
              the name was a link, so clicking the tier or status cell did
              nothing and read as a broken table. */}
          {shown.map((r) => (
            <tr
              key={r.asset_id}
              onClick={() => router.push(`/assets/${r.asset_id}`)}
              className="border-b border-[var(--line)] hover:bg-[var(--wash)] cursor-pointer"
            >
              <td className="py-2.5 pr-3">
                <Link href={`/assets/${r.asset_id}`} className="font-medium hover:text-[var(--accent)]">
                  {r.name || r.asset_id}
                </Link>
                <span className="ml-2 text-[13px] text-[var(--ink-soft)]">{r.asset_id}</span>
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

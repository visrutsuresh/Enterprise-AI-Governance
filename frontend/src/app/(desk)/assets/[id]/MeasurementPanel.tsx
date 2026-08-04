"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { API_BASE, api } from "@/lib/api";

type Rates = { n: number; selection_rate: number; tpr: number; fpr: number; precision: number };
type Computed = {
  period: string;
  n: number;
  protected_attribute: string;
  fairness: { rows: Record<string, Rates>; worst_group: string; best_group: string } & Record<string, number | string | object>;
  drift: { name: string; kind: string; psi: number; jsd: number; band: string }[];
  performance: { auc?: number; baseline_auc?: number; drop?: number };
};
type Metric = {
  label: string; short: string; threshold: number; better: string; needs_labels: boolean; plain: string;
};

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
// the three drift bands used to be green / amber / red, which in a monochrome
// skin collapsed into one identical black. Bar LENGTH now carries the severity
// and the band word says it outright.
const BAND_WEIGHT: Record<string, string> = {
  stable: "font-normal text-[var(--ink-soft)]",
  moderate: "font-semibold text-[var(--ink)]",
  significant: "font-extrabold text-[var(--ink)]",
};

export default function MeasurementPanel({
  assetId,
  onSaved,
}: {
  assetId: string;
  onSaved: (msg: string) => void;
}) {
  const [periods, setPeriods] = useState<{ period: string; computed: Computed }[]>([]);
  const [cat, setCat] = useState<Record<string, Metric>>({});
  const [metric, setMetric] = useState("dir");
  const [at, setAt] = useState(0);
  const [reason, setReason] = useState("");
  const [asking, setAsking] = useState(false);
  const [err, setErr] = useState("");
  const picker = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api(`/assets/${assetId}/measurements`)
      .then((r) => {
        setPeriods(r.periods);
        setCat(r.metrics_catalogue);
        setMetric(r.metric);
        setAt(Math.max(0, r.periods.length - 1)); // newest month by default
        setErr("");
      })
      .catch((e) => setErr(String(e)));
  }, [assetId]);

  useEffect(() => {
    load();
  }, [load]);

  async function bind() {
    if (!reason.trim()) {
      setErr("Say why this definition of fair fits this asset.");
      return;
    }
    try {
      await api(`/assets/${assetId}/fairness-metric`, {
        method: "PUT",
        body: JSON.stringify({ metric, reason }),
      });
      setAsking(false);
      setReason("");
      load();
      onSaved(`Bound to ${cat[metric].short}. The findings were rewritten against it.`);
    } catch (e) {
      setErr(String(e));
    }
  }

  async function uploadCsv(file: File) {
    const period = window.prompt("Which period is this? e.g. 2026-07");
    if (!period) return;
    // deliberately NOT the api() helper: that pins Content-Type to JSON, and a
    // multipart body must set its own header so the browser adds the boundary
    const body = new FormData();
    body.append("file", file);
    const res = await fetch(
      `${API_BASE}/assets/${assetId}/measurements/csv?period=${encodeURIComponent(period)}&protected_attribute=group`,
      { method: "POST", credentials: "include", body }
    );
    if (picker.current) picker.current.value = ""; // let the same file be re-picked after a failure
    if (!res.ok) {
      setErr(await res.text());
      return;
    }
    const r = await res.json();
    load();
    onSaved(
      `${r.rows_used} rows read, ${r.rows_ignored} ignored. Disparate impact ${r.computed.fairness.dir.toFixed(3)}.`
    );
  }

  const fileInput = (
    <input
      ref={picker}
      type="file"
      accept=".csv,text/csv"
      className="hidden"
      onChange={(e) => e.target.files?.[0] && uploadCsv(e.target.files[0])}
    />
  );

  if (periods.length === 0)
    return (
      <section className="panel p-7 space-y-3">
        <h2 className="text-[19px] font-bold" style={{ fontFamily: "var(--font-cabinet)" }}>
          Bias and drift
        </h2>
        <p className="text-[15px] text-[var(--ink-soft)] max-w-[62ch]">
          Nothing measured yet, and that is the honest answer rather than a broken one. Bias and
          drift are properties of what a model DID, not of how it was described, so until a month of
          decisions lands here there is nothing truthful to show. Drop a CSV of{" "}
          <span className="font-mono">group, prediction, label</span> and every number below is
          computed from it.
        </p>
        {err && <p className="text-[15px] text-[var(--danger)]">{err}</p>}
        {fileInput}
        <button className="btn" onClick={() => picker.current?.click()}>
          Upload a sample
        </button>
      </section>
    );

  const c = periods[at].computed;
  const f = c.fairness;
  const m = cat[metric];
  const value = f[metric] as number;
  const pass = m.better === "high" ? value >= m.threshold : value <= m.threshold;

  return (
    <section className="panel p-7 space-y-5">
      <div className="flex items-baseline gap-3 flex-wrap">
        <h2 className="text-[19px] font-bold" style={{ fontFamily: "var(--font-cabinet)" }}>
          Bias, measured
        </h2>
        <select
          value={at}
          onChange={(e) => setAt(Number(e.target.value))}
          className="field text-[15px] py-1"
        >
          {periods.map((p, i) => (
            <option key={p.period} value={i}>
              {p.period}
            </option>
          ))}
        </select>
        <span className="text-[15px] font-array text-[var(--ink-soft)]">
          n={c.n.toLocaleString()} &middot; by {c.protected_attribute}
        </span>
      </div>

      {err && <p className="text-[15px] text-[var(--danger)]">{err}</p>}

      <div
        className={`rounded-[3px] p-4 ${
          pass ? "border border-[var(--line)]" : "border-2 border-[var(--ink)] bg-[var(--wash)]"
        }`}
      >
        <div className="text-[15px] uppercase tracking-wide text-[var(--ink-soft)]">
          the definition this asset is held to
        </div>
        <div className="flex items-center gap-4 flex-wrap mt-1">
          <span
            className={`text-[38px] ${pass ? "font-semibold" : "font-extrabold"}`}
            style={{ fontFamily: "var(--font-cabinet)" }}
          >
            {value.toFixed(3)}
          </span>
          <span className="text-[15px] text-[var(--ink-soft)] flex-1 min-w-[220px]">
            {m.label}, threshold {m.better === "high" ? "at least" : "at most"} {m.threshold}.
            <br />
            {m.plain}
          </span>
          <span className={`badge ${pass ? "done" : "review"}`}>
            {pass ? "within threshold" : "breach"}
          </span>
        </div>
      </div>

      <div>
        <div className="flex items-center gap-2 flex-wrap">
          <select
            value={metric}
            onChange={(e) => {
              setMetric(e.target.value);
              setAsking(true);
            }}
            className="field text-[15px]"
          >
            {Object.entries(cat).map(([k, v]) => (
              <option key={k} value={k}>
                {v.label}
                {v.needs_labels ? " (needs ground truth)" : ""}
              </option>
            ))}
          </select>
          {asking && (
            <>
              <input
                autoFocus
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="why does this definition fit this asset?"
                className="field text-[15px] flex-1 min-w-[220px]"
              />
              <button className="btn" onClick={bind}>
                Bind it
              </button>
            </>
          )}
        </div>

        <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-3">
          {Object.entries(cat).map(([k, v]) => {
            const val = f[k] as number;
            const ok = v.better === "high" ? val >= v.threshold : val <= v.threshold;
            return (
              /* pass and fail were green vs red on these five tiles and nothing
                 else, so in monochrome all five read the same. A failing metric
                 is now the heavy one, and it says so. */
              <div
                key={k}
                className={`rounded-[3px] px-3 py-2 ${
                  ok ? "border border-[var(--line)]" : "border-2 border-[var(--ink)] bg-[var(--wash)]"
                }`}
              >
                <div className="text-[15px] font-array tracking-wider text-[var(--ink-soft)]">
                  {v.short}
                </div>
                <div
                  className={`text-[20px] ${ok ? "font-semibold" : "font-extrabold"}`}
                  style={{ fontFamily: "var(--font-cabinet)" }}
                >
                  {val.toFixed(3)}
                </div>
                {!ok && (
                  <div className="text-[15px] font-array tracking-wider text-[var(--ink)] mt-0.5">
                    BREACH
                  </div>
                )}
              </div>
            );
          })}
        </div>
        <p className="text-[15px] text-[var(--ink-soft)] mt-2 max-w-[64ch]">
          These cannot all hold at once unless every group has the same base rate. That is why the
          one above is a signed choice and not a default.
        </p>
      </div>

      <table className="w-full text-[15px]">
        <thead>
          <tr className="text-left text-[15px] font-array tracking-wider uppercase text-[var(--ink-soft)] border-b border-[var(--line)]">
            <th className="py-2">group</th>
            <th>n</th>
            <th>approved</th>
            <th>of those who deserved it</th>
            <th>false positives</th>
            <th>precision</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(f.rows).map(([g, r]) => (
            <tr
              key={g}
              className="border-b border-[var(--line)] last:border-0"
              style={g === f.worst_group ? { background: "var(--rust-wash)" } : undefined}
            >
              <td className="py-2 font-mono text-[15px]">{g}</td>
              <td className="text-[var(--ink-soft)]">{r.n.toLocaleString()}</td>
              <td className="font-semibold">{pct(r.selection_rate)}</td>
              <td>{pct(r.tpr)}</td>
              <td>{pct(r.fpr)}</td>
              <td>{pct(r.precision)}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="pt-4 border-t border-[var(--line)]">
        <h3 className="text-[15px] font-semibold">Drift, measured</h3>
        {c.drift.length === 0 ? (
          <p className="text-[15px] text-[var(--ink-soft)] mt-1 max-w-[62ch]">
            No drift signals in this snapshot. A CSV of decisions carries no feature distributions,
            so drift needs the fuller JSON payload with a reference window to compare against.
          </p>
        ) : (
          <>
            <table className="w-full text-[15px] mt-2">
              <thead>
                <tr className="text-left text-[15px] font-array tracking-wider uppercase text-[var(--ink-soft)] border-b border-[var(--line)]">
                  <th className="py-2">signal</th>
                  <th>kind</th>
                  <th>psi</th>
                  <th className="w-[34%]">shift</th>
                </tr>
              </thead>
              <tbody>
                {c.drift.map((d) => (
                  <tr key={d.name} className="border-b border-[var(--line)] last:border-0">
                    <td className="py-2 font-mono text-[15px]">{d.name}</td>
                    <td className="text-[var(--ink-soft)] text-[15px]">{d.kind}</td>
                    <td className={BAND_WEIGHT[d.band] ?? ""}>{d.psi.toFixed(3)}</td>
                    <td>
                      <div className="h-[7px] rounded-[2px] bg-[var(--line)] overflow-hidden max-w-[120px]">
                        <div
                          className="h-full bg-[var(--ink)]"
                          style={{ width: `${Math.min(100, (d.psi / 0.5) * 100)}%` }}
                          title={`PSI ${d.psi.toFixed(3)} (${d.band})`}
                        />
                      </div>
                      <span className={`text-[15px] ${BAND_WEIGHT[d.band] ?? "text-[var(--ink-soft)]"}`}>
                        {d.band}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="text-[15px] text-[var(--ink-soft)] mt-2 max-w-[64ch]">
              Under 0.10 is stable, 0.10 to 0.25 moderate, above 0.25 significant.
              {c.performance.auc != null && (
                <>
                  {" "}
                  Accuracy is {c.performance.auc} against {c.performance.baseline_auc} at sign-off,
                  down {((c.performance.drop ?? 0) * 100).toFixed(0)} points. Labels arrive months
                  late, so this is the truest signal and the slowest.
                </>
              )}
            </p>
          </>
        )}
      </div>

      {fileInput}
      <button className="btn ghost" onClick={() => picker.current?.click()}>
        Add another period from a CSV
      </button>
    </section>
  );
}

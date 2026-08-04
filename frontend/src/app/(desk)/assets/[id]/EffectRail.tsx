"use client";
import { useEffect, useRef, useState } from "react";

/* The C idea, in one file.
   In a governance tool the point of an edit is never the edit, it is what the
   edit does to the verdict. So this column never scrolls away, and any row that
   MOVED says what it was before you touched it. */

type Snapshot = Record<string, string | number>;

// only the slice of the asset state this column reads. Typing it narrowly is
// the difference between "the rail broke" and "the rail told us what broke".
export type RailState = {
  risk_tier?: string | null;
  field_source?: Record<string, unknown>;
  audit?: { step: string }[];
  asset?: {
    assessment?: {
      risk_tier?: string;
      decision?: string;
      findings?: { severity?: string }[];
    };
  };
};

// no hue in this skin: a value that is bad news is set in heavier type, and
// the label beside it already says what it is. "pending" is deliberately NOT
// treated as good news, which the old green did.
const ALARM = "font-extrabold";
const CALM = "font-semibold";

export default function EffectRail({
  state,
  metric,
}: {
  state: RailState;
  metric: { short: string; value: number; pass: boolean } | null;
}) {
  const assessment = state.asset?.assessment ?? {};
  const findings: { severity?: string }[] = assessment.findings ?? [];
  const tier = String(state.risk_tier || assessment.risk_tier || "").toLowerCase();

  const snap: Snapshot = {
    tier: tier || "unassigned",
    decision: assessment.decision ?? "pending",
    findings: findings.length,
    serious: findings.filter((f) => f.severity === "high").length,
    corrected: Object.keys(state.field_source ?? {}).length,
  };
  if (metric) snap[metric.short] = metric.value.toFixed(3);

  const prev = useRef<Snapshot | null>(null);
  const [was, setWas] = useState<Snapshot>({});
  const key = JSON.stringify(snap);

  useEffect(() => {
    const before = prev.current;
    prev.current = snap;
    if (!before) return;
    const moved: Snapshot = {};
    for (const k of Object.keys(snap)) {
      if (before[k] !== undefined && String(before[k]) !== String(snap[k])) moved[k] = before[k];
    }
    if (!Object.keys(moved).length) return;
    // The lint rule objects to setState inside an effect, and it is usually
    // right. This is the exception it exists for: the rail has no way to know a
    // number moved except by watching it move, and the highlight is a timed
    // animation, not derived state. It runs only when a value actually changed.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setWas(moved);
    // the "was" note fades on its own: it is a nudge about what just happened,
    // not a second permanent number competing with the first
    const t = setTimeout(() => setWas({}), 5000);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const row = (k: string, label: string, value: React.ReactNode, alarm?: boolean) => (
    <div
      key={k}
      className="flex justify-between items-baseline py-2.5 border-t border-[var(--line)] first:border-t-0 px-2 -mx-2 rounded transition-colors"
      style={was[k] !== undefined ? { background: "var(--accent-wash)" } : undefined}
    >
      <span className="text-[12.5px] text-[var(--ink-soft)]">{label}</span>
      <span className="text-right">
        <span
          className={`text-[15px] ${alarm ? ALARM : CALM}`}
          style={{ fontFamily: "var(--font-cabinet)" }}
        >
          {value}
        </span>
        {was[k] !== undefined && (
          <span className="block font-array text-[9px] tracking-wider text-[var(--accent)]">
            was {was[k]}
          </span>
        )}
      </span>
    </div>
  );

  const chain: { step: string }[] = state.audit ?? [];

  return (
    <div className="lg:sticky lg:top-5 lg:border-l border-[var(--line)] lg:pl-6 pt-6 lg:pt-0 border-t lg:border-t-0">
      <div className="font-array text-[10px] tracking-[0.16em] uppercase text-[var(--ink-soft)] mb-3">
        what the record adds up to
      </div>
      {row("tier", "EU AI Act tier", snap.tier, tier === "high" || tier === "unacceptable")}
      {row("decision", "decision", snap.decision, snap.decision === "flagged")}
      {row("findings", "open findings", snap.findings)}
      {row("serious", "of them serious", snap.serious, Boolean(snap.serious))}
      {metric && row(metric.short, metric.short, snap[metric.short], !metric.pass)}
      {row("corrected", "fields corrected", snap.corrected)}

      <div className="mt-7">
        <div className="font-array text-[10px] tracking-[0.16em] uppercase text-[var(--ink-soft)] mb-2">
          last on the trail
        </div>
        <ul>
          {chain.slice(-3).map((e, i, arr) => (
            <li
              key={i}
              title={e.step}
              className={`font-array text-[10px] leading-relaxed py-1.5 border-t border-[var(--line)] truncate ${
                i === arr.length - 1 ? "text-[var(--accent)]" : "text-[var(--ink-soft)]"
              }`}
            >
              {e.step}
            </li>
          ))}
          {chain.length === 0 && (
            <li className="font-array text-[10px] text-[var(--ink-soft)]">
              empty chain: a seeded fixture, no pipeline ever ran on it
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}

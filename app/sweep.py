"""The nightly sweep: a plain loop, NOT a graph (D41).

Per asset: model_monitoring. Once across the estate: regulatory_intel.
Then: audit_reporting. New flags land on the same store and the same hash
chain the per-asset path uses, so the control tower opens with overnight
findings on it. Invoked by POST /sweep/run (a real cron has no demo value).
"""

from app import agents, audit, packs, store
from app.state import risk_rollup


def _estate_stats() -> dict:
    rows = store.list_all()
    tiers, flagged, open_findings = {}, 0, 0
    for r in rows:
        if r["risk_tier"]:
            tiers[r["risk_tier"]] = tiers.get(r["risk_tier"], 0) + 1
        if r["open_findings"]:
            flagged += 1
            open_findings += r["open_findings"]
    return {"assets": len(rows), "by_tier": tiers, "assets_with_open_findings": flagged,
            "open_findings": open_findings}


def _append_sweep_result(asset_id: str, agent_name: str, findings: list, note: str) -> None:
    # fold sweep output into the asset's stored state: findings join the
    # assessment, the rollup recomputes, and the visit lands on the hash chain
    state = store.get(asset_id)
    if state is None:
        return
    asset = dict(state.get("asset", {}))
    assessment = dict(asset.get("assessment") or {})
    all_findings = list(assessment.get("findings", [])) + findings
    assessment["findings"] = all_findings
    assessment["risk"] = risk_rollup(all_findings)
    if findings:
        assessment["decision"] = "flagged"
    asset["assessment"] = assessment
    state["asset"] = asset
    state["risk"] = assessment["risk"]
    if findings:
        state["decision"] = "flagged"
    state["audit"] = audit.chain(state.get("audit") or [], [f"{agent_name}: {note}"])
    store.save(state)


def rescore_policy() -> dict:
    """The pack-swap moment (NFR-1): re-apply the ACTIVE policy pack's rules to
    every asset, deterministically, $0. Old policy findings are replaced with
    the new pack's; findings by other inspectors (framework, drift) are kept.
    Honest scope: EU-tier re-tiering needs the model, so tiers do not move here."""
    pack = packs.load_policy_pack()
    rows = store.list_all()
    changed = 0
    for r in rows:
        state = store.get(r["asset_id"])
        if state is None:
            continue
        asset = dict(state.get("asset", {}))
        assessment = dict(asset.get("assessment") or {})
        if not assessment:
            continue  # never invent an assessment for an unassessed asset
        old = assessment.get("findings", [])
        kept = [f for f in old if f.get("inspector") != "policy_compliance"]
        fired = [rule for rule in pack["rules"] if packs.fires(rule, asset)]
        for n, rule in enumerate(fired, start=1):
            kept.append({
                "finding_id": f"f-{r['asset_id']}-pol-{n}",
                "inspector": "policy_compliance",
                "control_id": rule["id"],
                "severity": rule["severity"],
                "plain": rule["title"],
                "evidence": f"rule {rule['id']} of pack {pack['pack_id']} matches this asset's record",
                "remediation": f"Bring the asset in line with {rule['id']} or retire it.",
                "status": "open",
            })
        if {f["finding_id"] for f in kept} == {f.get("finding_id") for f in old}:
            continue
        assessment["findings"] = kept
        assessment["risk"] = risk_rollup(kept)
        assessment["decision"] = "flagged" if kept else "compliant"
        asset["assessment"] = assessment
        state["asset"] = asset
        state["risk"] = assessment["risk"]
        state["decision"] = assessment["decision"]
        state["audit"] = audit.chain(state.get("audit") or [],
                                     [f"pack_swap re-score against {pack['pack_id']}: {len(fired)} policy finding(s)"])
        store.save(state)
        changed += 1
    return {"pack": pack["pack_id"], "assets_rescored": changed, "estate": _estate_stats()}


def run_sweep(limit: int = 10) -> dict:
    """limit caps the per-asset monitoring pass: each asset is one model call,
    and 185 calls is a bill, not a demo. Un-swept assets are counted honestly."""
    rows = store.list_all()
    target = rows[:limit]
    new_findings, checked = 0, []
    for r in target:
        state = store.get(r["asset_id"])
        if state is None:
            continue
        found, note = agents.model_monitoring_agent(state)
        _append_sweep_result(r["asset_id"], "model_monitoring", found, note)
        new_findings += len(found)
        checked.append({"asset_id": r["asset_id"], "note": note})

    stats = _estate_stats()
    notes = agents.regulatory_intel_agent(f"Estate summary: {stats}")

    sweep_summary = (f"Tonight's sweep: {len(checked)} of {len(rows)} assets monitored "
                     f"({len(rows) - len(target)} not swept tonight), {new_findings} new drift finding(s), "
                     f"regulatory notes: {notes}\nEstate: {stats}")
    report = agents.audit_reporting_agent(sweep_summary)

    return {
        "monitored": len(checked),
        "not_swept": len(rows) - len(target),
        "new_findings": new_findings,
        "checked": checked,
        "regulatory_notes": notes,
        "report": report,
        "estate": stats,
    }


# --- executive dashboard metrics (the five PDF categories) -------------------
# Every REAL metric is computed from the live estate right here; each formula is
# named inline. A metric with NO honest source in the estate is returned with
# {"sample": True} so the UI badges it and we never pass a made-up number off as
# measured (the truthfulness rule). Reuses store.list_metrics_rows for one read.

_REVIEW_STATUSES = ("processing", "registered")


def _pct(part: int, whole: int) -> int:
    return round(part / whole * 100) if whole else 0


def _estate_metrics() -> dict:
    rows = store.list_metrics_rows()
    total = len(rows)

    # portfolio: lifecycle + status counts straight off the label columns
    production = sum(1 for r in rows if (r["lifecycle"] or "") == "production")
    under_review = sum(1 for r in rows if (r["status"] or "") in _REVIEW_STATUSES)

    # risk tier + decision tallies
    high_risk = sum(1 for r in rows if (r["risk_tier"] or "") in ("high", "unacceptable"))
    compliant = sum(1 for r in rows if r["decision"] == "compliant")
    flagged = sum(1 for r in rows if r["decision"] == "flagged")
    assessed = compliant + flagged
    pending = total - assessed

    # findings, broken down by the inspector that raised them and by status
    by_inspector: dict = {}
    total_findings = 0
    open_findings = 0
    bias_findings = 0
    for r in rows:
        for f in (r["findings"] or []):
            insp = f.get("inspector", "")
            total_findings += 1
            by_inspector[insp] = by_inspector.get(insp, 0) + 1
            if f.get("status", "open") == "open":
                open_findings += 1
            if insp == "responsible_ai":
                blob = f"{f.get('plain', '')} {f.get('evidence', '')}".lower()
                if "bias" in blob or "fairness" in blob or "discriminat" in blob:
                    bias_findings += 1

    policy_violations = by_inspector.get("policy_compliance", 0)
    third_party = by_inspector.get("security_third_party", 0)
    drift = by_inspector.get("model_monitoring", 0)

    # human oversight: share of PRODUCTION assets that name a human overseer
    prod_rows = [r for r in rows if (r["lifecycle"] or "") == "production"]
    prod_with_oversight = sum(1 for r in prod_rows if (r["human_oversight"] or "").strip())

    def real(value, detail, unit=""):
        return {"value": value, "detail": detail, "unit": unit}

    def sample(value, detail, unit=""):
        return {"value": value, "sample": True, "detail": detail, "unit": unit}

    return {
        "portfolio": {
            "total_use_cases": real(total, "count of registered AI assets"),
            "in_production": real(production, "assets with lifecycle = production"),
            "under_review": real(under_review, "status processing or registered (not yet assessed)"),
            "adoption_rate": real(_pct(production, total), "production / total assets", "%"),
        },
        "risk": {
            "high_risk_systems": real(high_risk, "assets tiered high or unacceptable"),
            "open_issues": real(open_findings, "findings with status open across the estate"),
            "policy_violations": real(policy_violations, "findings from the policy_compliance inspector"),
            "third_party_risks": real(third_party, "findings from the security_third_party inspector"),
        },
        "compliance": {
            "compliance_score": real(_pct(compliant, assessed), "compliant / assessed assets", "%"),
            "regulatory_readiness": sample(78, "no regulatory-readiness signal is tracked per asset yet", "%"),
            "audit_findings": real(total_findings, "total findings on record across all assessments"),
            "approval_status": real(compliant, f"{compliant} compliant vs {flagged} flagged ({pending} pending decision)"),
        },
        "responsible_ai": {
            "bias_assessment": real(bias_findings, "open responsible_ai findings citing bias or fairness"),
            "explainability_coverage": sample(64, "explainability metadata is not captured per asset yet", "%"),
            "human_oversight": real(_pct(prod_with_oversight, len(prod_rows)),
                                    f"{prod_with_oversight}/{len(prod_rows)} production assets name a human overseer", "%"),
            "model_transparency": sample(71, "no transparency / model-card score is captured yet"),
        },
        "operational": {
            "model_performance": sample(92, "live model-performance telemetry is not wired into the estate", "%"),
            "model_drift_incidents": real(drift, "findings from the model_monitoring sweep agent"),
            "security_findings": real(third_party, "findings from the security_third_party inspector"),
            "sla_compliance": sample(88, "no SLA timers are recorded in the estate yet", "%"),
        },
    }

"""bench.py's scorers are pure functions: prove them on fabricated states."""

from conftest import make_finding

from app.audit import chain
from bench import aggregate, score_asset

ENTRY = {
    "asset": {"asset_id": "AI-9001"},
    "expected": {"risk_tier": "high", "policy_violations": ["POL-02", "POL-03"]},
}


def _final(tier="High", controls=("POL-02", "POL-03"), status="assessed"):
    findings = [make_finding(control_id=c) for c in controls]
    log = chain([], ["inventory done", "orchestrate done: 5 inspectors", "fan-in: kept", "decision: flagged"])
    return {
        "risk_tier": tier,
        "status": status,
        "asset": {"assessment": {"findings": findings}},
        "audit": log,
    }


def test_perfect_run_scores_perfect():
    s = score_asset(_final(), ENTRY)
    assert s["tier_ok"] and s["recall"] == 1.0 and s["precision"] == 1.0 and s["audit_complete"]


def test_missed_violation_hits_recall_not_precision():
    s = score_asset(_final(controls=("POL-02",)), ENTRY)
    assert s["recall"] == 0.5 and s["precision"] == 1.0 and s["missed"] == ["POL-03"]


def test_hallucinated_flag_hits_precision():
    s = score_asset(_final(controls=("POL-02", "POL-03", "POL-99")), ENTRY)
    assert s["recall"] == 1.0 and round(s["precision"], 2) == 0.67 and s["extra"] == ["POL-99"]


def test_wrong_tier_and_tampered_chain_detected():
    f = _final(tier="minimal")
    f["audit"][2]["step"] = "fan-in: forged"
    s = score_asset(f, ENTRY)
    assert not s["tier_ok"] and not s["audit_complete"]


def test_aggregate_only_counts_completed():
    good = score_asset(_final(), ENTRY)
    dead = score_asset(_final(status="error"), ENTRY)
    summary = aggregate([good, dead])
    assert summary["assets"] == 2 and summary["completed"] == 1
    assert summary["tier_accuracy"] == 1.0

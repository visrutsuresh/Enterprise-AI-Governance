"""Governance state: the case file every agent adds pages to.

The shapes that flow through GovernanceState are plain dicts, same
discipline as Papyrus: they survive JSON round trips untouched.

The asset record shape lives in app/schemas.py (AssetRecord).

Finding = {
    "finding_id": "f-AI-0042-pol-1",
    "inspector": "policy_compliance",     # one of INSPECTORS below
    "control_id": "POL-03",               # the pack rule or framework control it pins to
    "severity": "high" | "medium" | "low",
    "plain": "This model reads credit history but has no recorded bias test.",
    "evidence": "data_touched includes 'credit history'; no bias_test field",
    "remediation": "Run a fairness assessment before the next release.",
    "status": "open",
}

Casing trap (from CLAUDE.md): the risk tier comes back as the model wrote
it ("High", "Unacceptable"). Every reader must .lower() it.
"""

import operator
from typing import Annotated, TypedDict

from app.audit import chain

INSPECTORS = ["policy_compliance", "risk_assessment", "data_governance", "responsible_ai", "security_third_party"]

# the four EU AI Act tiers, worst first (framework pack detail lives in data/)
RISK_TIERS = ("unacceptable", "high", "limited", "minimal")


class GovernanceState(TypedDict):
    asset_id: str
    status: str  # processing | assessed | flagged | error
    stage: str  # narration key: intake | orchestrating | inspecting | rolling_up | done
    description: str  # the messy registration text the inventory agent canonicalises
    asset: dict  # the canonical AssetRecord (schemas.py)
    applicable_inspectors: list  # picked by the orchestrator (D46); default = all five
    findings_raw: Annotated[list, operator.add]  # inspectors append here in parallel
    inspector_reports: Annotated[list, operator.add]  # [{"inspector": name, "status": "ok"|"failed", "note": str}]
    risk_tier: str  # EU AI Act tier assigned by risk_assessment, lowercased at fan-in
    risk: dict  # rollup: {"level": high|medium|low, "score": int, "why": str}
    decision: str  # compliant | flagged, plain code, never auto-block (D31)
    audit: Annotated[list, chain]
    error: str | None


REQUIRED_FINDING_FIELDS = ("finding_id", "inspector", "control_id", "severity", "plain", "evidence", "remediation")


def valid_finding(f: dict) -> bool:
    # the gate that drops malformed inspector output before it reaches the record
    return (
        all(f.get(k) for k in REQUIRED_FINDING_FIELDS)
        and f["inspector"] in INSPECTORS
        and f["severity"] in ("high", "medium", "low")
    )


def risk_rollup(findings: list) -> dict:
    # deterministic on purpose: the agents never write the rollup, so it stays benchable
    sevs = [f["severity"] for f in findings]
    score = min(100, sevs.count("high") * 25 + sevs.count("medium") * 10 + sevs.count("low") * 4)
    level = "high" if "high" in sevs else ("medium" if "medium" in sevs else "low")
    why = f"{sevs.count('high')} serious, {sevs.count('medium')} medium, {sevs.count('low')} minor issues"
    return {"level": level, "score": score, "why": why}

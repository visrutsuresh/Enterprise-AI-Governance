"""The twelve governance agents share this machinery.

Phase 3 holds only the shared header: context sheet, FINDING_RULES prompt
block, _stamp, _run_inspector, guarded. The five inspectors, the sweep
agents and the on-demand agents land in Phases 4-7, each a react() loop
distinguished by its system prompt and allowed-tools list (D40).
"""

from app.agents_base import react
from app.state import valid_finding

_INSPECTOR_CODE = {
    "policy_compliance": "pol",
    "risk_assessment": "rsk",
    "data_governance": "dat",
    "responsible_ai": "rai",
    "security_third_party": "sec",
}


def _asset_sheet(state: dict) -> str:
    # the asset record as labelled lines; findings must trace to these facts
    a = state.get("asset", {})
    lines = [f"{k}: {a.get(k)!r}" for k in (
        "asset_id", "type", "name", "owner", "purpose", "lifecycle",
        "deployment", "data_touched", "third_party", "human_oversight")]
    return "Asset under assessment:\n" + "\n".join(lines)


FINDING_RULES = """
<finding> is this exact JSON object, every field filled:
  {"control_id": "POL-03", "severity": "high",
   "plain": "This model reads customer credit history but has no recorded bias test.",
   "evidence": "data_touched includes 'credit history'; no fairness assessment on record",
   "remediation": "Run a fairness assessment and attach it before the next release."}
Field rules (a finding missing any of these is thrown away unseen):
  control_id:  the id of the SPECIFIC pack rule or framework control the asset breaks,
               exactly as printed in the pack (e.g. POL-03, EU-H-02). Never invent one.
  severity:    high, medium or low, lowercase.
  plain:       ONE sentence a non-specialist feels in their gut. No jargon in it.
  evidence:    which asset fields, quoted, make the rule fire.
  remediation: the concrete step that would clear the finding.
Severity guide: high = people's rights, money or the law at risk; medium = a real but
survivable gap; low = untidy but harmless.
Flag only what you can pin to a control_id with evidence. An empty findings list is a valid answer.
"""


def _stamp(f, name: str, asset_id: str, n: int):
    # tag one model finding with its inspector, a stable id, lowercase severity
    if not isinstance(f, dict):
        return None
    f = dict(f)
    f["inspector"] = name
    f["severity"] = str(f.get("severity", "")).lower()
    f["finding_id"] = f"f-{asset_id}-{_INSPECTOR_CODE[name]}-{n}"
    f.setdefault("status", "open")
    return f


def _run_inspector(name: str, system: str, state: dict, allowed: list[str]) -> tuple[dict, dict]:
    # run one inspector to its finish JSON; keep only findings that pass valid_finding
    result = react(system, _asset_sheet(state), allowed)
    raw = result.get("findings", []) or []
    asset_id = state.get("asset_id", "unknown")
    kept, dropped = [], 0
    for n, f in enumerate(raw, start=1):
        f = _stamp(f, name, asset_id, n)
        if f is not None and valid_finding(f):
            kept.append(f)
        else:
            dropped += 1
    note = f"dropped {dropped} invalid finding(s)" if dropped else ""
    update = {
        "findings_raw": kept,
        "inspector_reports": [{"inspector": name, "status": "ok", "note": note}],
        "audit": [f"{name} done"],
    }
    return update, result


def guarded(name: str, fn, state: dict) -> dict:
    # degrade, don't die: a hung or crashed inspector becomes a "failed" report,
    # the other inspectors and fan-in still run, the UI says so honestly
    try:
        return fn(state)
    except Exception as e:
        return {
            "findings_raw": [],
            "inspector_reports": [{"inspector": name, "status": "failed", "note": str(e)}],
            "audit": [f"{name} failed: {e}"],
        }

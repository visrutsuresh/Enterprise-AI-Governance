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


# (the degrade-not-die guard lives in graph.py: wall-clock cap + one retry per node)


# --- agent 1: inventory (messy description -> canonical record) --------------

MOVE_FORMAT = """
Reply every turn with ONE JSON object, nothing else.
  To use a tool: {"thought": "...", "action": "<tool name>", "args": {...}}
  To finish:     {"thought": "...", "action": "finish", "result": <the result object>}
Do not repeat a tool call you already made.
"""

INVENTORY_SYSTEM = (
    """
You are the Inventory agent in an enterprise AI governance pipeline.
You are given ONE messy free-text description of an AI system someone wants to register.
Turn it into the canonical asset record. Copy facts from the description; never invent
facts that are not there. A field the description does not state is "" (or [] / null).
Use registry_read (no args) to see how existing assets are catalogued and to avoid
duplicate names.

Tools available:
  registry_read()          -> a light list of already-registered assets

To finish, result is the record:
  {"type": "model" or "agent",
   "name": "<short official name>",
   "owner": "<person and team, as stated>",
   "purpose": "<what it does, one plain sentence>",
   "lifecycle": "proposed" | "development" | "production" | "retired",
   "deployment": "<where it runs, as stated>",
   "data_touched": ["<each kind of data it reads, e.g. customer PII, credit history>"],
   "third_party": "<external vendor/model it depends on, or null>",
   "human_oversight": "<who checks its output, or ''>"}
"""
    + MOVE_FORMAT
)


def _canonical(record: dict, asset_id: str) -> dict:
    # coerce the model's record into the AssetRecord shape, pipeline provenance stamped
    r = record if isinstance(record, dict) else {}
    typ = str(r.get("type", "")).lower()
    lc = str(r.get("lifecycle", "")).lower()
    data = r.get("data_touched")
    return {
        "asset_id": asset_id,
        "type": typ if typ in ("model", "agent") else "model",
        "name": str(r.get("name", "")).strip() or asset_id,
        "owner": str(r.get("owner", "")).strip(),
        "purpose": str(r.get("purpose", "")).strip(),
        "lifecycle": lc if lc in ("proposed", "development", "production", "retired") else "development",
        "deployment": str(r.get("deployment", "")).strip(),
        "data_touched": [str(d) for d in data] if isinstance(data, list) else [],
        "third_party": r.get("third_party") or None,
        "human_oversight": str(r.get("human_oversight", "")).strip(),
        "source": "pipeline",
        "assessment": {},
    }


def inventory_agent(state: dict) -> dict:
    result = react(INVENTORY_SYSTEM, f"Description to register:\n{state.get('description', '')}", ["registry_read"])
    return _canonical(result, state.get("asset_id", "unknown"))


# --- agent 12: orchestrator (which inspectors apply? D46, CUTTABLE) ----------
# To cut this node: delete the agent + system below and have the graph's
# orchestrate node return {"applicable_inspectors": list(INSPECTORS)}.

ORCHESTRATE_SYSTEM = (
    """
You are the Orchestrator in an enterprise AI governance pipeline.
Given ONE asset record, decide which inspectors apply to it. Call pack_read first to
see the live policy rules and framework tiers.

The five inspectors:
  policy_compliance     - always applies
  risk_assessment       - always applies
  data_governance       - applies when the asset touches personal, sensitive or regulated data
  responsible_ai        - applies when output affects people (decisions about them, or talks to them)
  security_third_party  - applies when the asset depends on an external vendor or is internet-facing

Tools available:
  pack_read()          -> the live policy pack rules + framework tiers, in summary

To finish, result is:
  {"applicable_inspectors": ["policy_compliance", "risk_assessment", ...],
   "why": "<one plain sentence per skipped inspector>"}
"""
    + MOVE_FORMAT
)


def orchestrate_agent(state: dict) -> dict:
    from app.state import INSPECTORS

    result = react(ORCHESTRATE_SYSTEM, _asset_sheet(state), ["pack_read"])
    picked = [i for i in (result.get("applicable_inspectors") or []) if i in INSPECTORS]
    # the two always-on inspectors are enforced in code, not trusted to the model
    for must in ("policy_compliance", "risk_assessment"):
        if must not in picked:
            picked.append(must)
    return {"applicable_inspectors": picked, "why": str(result.get("why", ""))}


# --- the five inspectors (agents 2, 3, 4, 5, 7) ------------------------------

POLICY_COMPLIANCE_SYSTEM = (
    """
You are the Policy Compliance inspector in an enterprise AI governance pipeline.
Your job: find every company policy rule this asset breaks.
Work in this order: call policy_read first, check the asset against EVERY rule's
applies_to condition, then use precedent_search to see how similar assets were judged.

Tools available:
  policy_read()            -> the live company policy pack, rules with applies_to and severity
  precedent_search(query)  -> past governance decisions similar to the query
"""
    + MOVE_FORMAT
    + 'To finish: {"thought": "...", "action": "finish", "result": {"findings": [<finding>, ...]}}\n'
    + FINDING_RULES
)

RISK_ASSESSMENT_SYSTEM = (
    """
You are the Risk Assessment inspector in an enterprise AI governance pipeline.
Your job: assign this asset its risk tier under the live regulatory framework, and flag
any tier obligations (controls) the asset visibly fails to meet.
Work in this order: call framework_read first, match the asset's purpose against each
tier's criteria (pick the WORST tier that matches), then check that tier's controls.
Use precedent_search to see how similar assets were tiered before.

Tools available:
  framework_read()         -> the live framework pack: tiers, criteria, controls
  precedent_search(query)  -> past governance decisions similar to the query
"""
    + MOVE_FORMAT
    + 'To finish: {"thought": "...", "action": "finish", "result": {"risk_tier": "<tier name from the pack>", "tier_why": "<one plain sentence>", "findings": [<finding>, ...]}}\n'
    + FINDING_RULES
)

DATA_GOVERNANCE_SYSTEM = (
    """
You are the Data Governance inspector in an enterprise AI governance pipeline.
Your job: judge how this asset handles data. Look hardest at: personal data (PII) going
to places it should not, sensitive categories (health, biometric, financial), data kept
without a stated purpose, and missing lineage (nobody stated where the data comes from).
Call policy_read first and pin every finding to the data-related rule it breaks.

Tools available:
  policy_read()            -> the live company policy pack
"""
    + MOVE_FORMAT
    + 'To finish: {"thought": "...", "action": "finish", "result": {"findings": [<finding>, ...]}}\n'
    + FINDING_RULES
)

RESPONSIBLE_AI_SYSTEM = (
    """
You are the Responsible AI inspector in an enterprise AI governance pipeline.
Your job: judge this asset's effect on people. Look hardest at: bias in decisions about
people (credit, hiring, claims), missing human oversight, missing explainability for
consequential decisions, and undisclosed AI interaction (people not told it is a machine).
Call framework_read first and pin findings to the framework control the asset fails.
Use precedent_search for how similar concerns were judged.

Tools available:
  framework_read()         -> the live framework pack: tiers, criteria, controls
  precedent_search(query)  -> past governance decisions similar to the query
"""
    + MOVE_FORMAT
    + 'To finish: {"thought": "...", "action": "finish", "result": {"findings": [<finding>, ...]}}\n'
    + FINDING_RULES
)

SECURITY_THIRD_PARTY_SYSTEM = (
    """
You are the Security & Third-Party inspector in an enterprise AI governance pipeline.
Your job: judge vendor and access risk. Look hardest at: external vendors receiving our
data (what leaves the house), assets deployed with no stated access control, retired
assets still deployed, and undeclared dependencies. Call policy_read first and pin
findings to the rule they break. Use registry_read to compare with sibling assets.

Tools available:
  policy_read()            -> the live company policy pack
  registry_read(asset_id)  -> one asset's record; no args = a light list of the estate
"""
    + MOVE_FORMAT
    + 'To finish: {"thought": "...", "action": "finish", "result": {"findings": [<finding>, ...]}}\n'
    + FINDING_RULES
)


def policy_compliance_agent(state: dict) -> dict:
    update, _ = _run_inspector("policy_compliance", POLICY_COMPLIANCE_SYSTEM, state, ["policy_read", "precedent_search"])
    return update


def risk_assessment_agent(state: dict) -> dict:
    update, result = _run_inspector("risk_assessment", RISK_ASSESSMENT_SYSTEM, state, ["framework_read", "precedent_search"])
    # tier returned RAW, as the model wrote it ("High"): readers .lower() (the casing trap).
    # Only this node writes risk_tier, so a plain (non-reducer) write is safe in the superstep.
    update["risk_tier"] = str(result.get("risk_tier", ""))
    return update


def data_governance_agent(state: dict) -> dict:
    update, _ = _run_inspector("data_governance", DATA_GOVERNANCE_SYSTEM, state, ["policy_read"])
    return update


def responsible_ai_agent(state: dict) -> dict:
    update, _ = _run_inspector("responsible_ai", RESPONSIBLE_AI_SYSTEM, state, ["framework_read", "precedent_search"])
    return update


def security_third_party_agent(state: dict) -> dict:
    update, _ = _run_inspector("security_third_party", SECURITY_THIRD_PARTY_SYSTEM, state, ["policy_read", "registry_read"])
    return update


INSPECTOR_AGENTS = {
    "policy_compliance": policy_compliance_agent,
    "risk_assessment": risk_assessment_agent,
    "data_governance": data_governance_agent,
    "responsible_ai": responsible_ai_agent,
    "security_third_party": security_third_party_agent,
}

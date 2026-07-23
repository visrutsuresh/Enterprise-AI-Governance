"""The per-asset pipeline: inventory -> orchestrate -> fan-out -> fan_in -> decide.
The ORDER is code; the judgement lives inside each agent (bounded autonomy, D31).
Fan-in and decide are plain code on purpose: the agents never write the rollup,
so the rollup stays deterministic and benchable."""

from concurrent.futures import ThreadPoolExecutor

from langgraph.graph import END, START, StateGraph

from app import agents, store
from app.state import INSPECTORS, GovernanceState, risk_rollup, valid_finding


def initial_state(asset_id: str, description: str) -> dict:
    return {
        "asset_id": asset_id,
        "status": "processing",
        "stage": "intake",
        "description": description,
        "asset": {},
        "applicable_inspectors": [],
        "findings_raw": [],
        "inspector_reports": [],
        "risk_tier": "",
        "risk": {},
        "decision": "",
        "audit": [],
        "error": None,
    }


# --- narration --------------------------------------------------------------


def _stage(state: GovernanceState, stage: str) -> None:
    """Write the stage where the control tower's polling can see it, mid-run."""
    try:
        store.set_stage(state["asset_id"], stage)
    except Exception:
        pass  # narration must never kill an assessment (bench runs have no DB row)
    print(f"[pipeline] {state['asset_id']} stage={stage}", flush=True)


# --- the guard --------------------------------------------------------------

# the lane serializes on one GPU, so a parallel inspector's wall-clock includes
# every call queued ahead of it; 1200 fits five inspectors at ~2-3 min each
def guarded(fn, name: str, timeout_s: int = 1200):
    """Wall-clock cap plus one retry around a node. Inspectors degrade on a
    double failure; spine nodes stamp status=error. The graph never crashes."""

    def node(state: GovernanceState) -> dict:
        err = "unknown failure"
        for attempt in (1, 2):
            print(f"[pipeline] {state['asset_id']} {name} attempt {attempt}", flush=True)
            pool = ThreadPoolExecutor(max_workers=1)
            try:
                out = pool.submit(fn, state).result(timeout=timeout_s)
                print(f"[pipeline] {state['asset_id']} {name} done", flush=True)
                return out
            except Exception as e:
                err = str(e) or type(e).__name__
                print(f"[pipeline] {state['asset_id']} {name} attempt {attempt} failed: {err}", flush=True)
            finally:
                pool.shutdown(wait=False)
        if name in INSPECTORS:
            return {
                "inspector_reports": [{"inspector": name, "status": "failed", "note": err}],
                "audit": [f"{name} failed: {err}"],
            }
        return {
            "status": "error",
            "error": f"The assessment stopped at the {name} step after two attempts: {err}",
            "audit": [f"{name} failed: {err}"],
        }

    return node


# --- spine nodes ------------------------------------------------------------


def inventory_node(state: GovernanceState) -> dict:
    _stage(state, "intake")
    if not (state.get("description") or "").strip():
        return {"status": "error", "error": "Nothing to register: the description was empty.",
                "audit": ["inventory failed: empty description"]}
    asset = agents.inventory_agent(state)
    return {"asset": asset, "audit": [f"inventory done: {asset['type']} '{asset['name']}', lifecycle {asset['lifecycle']}"]}


def orchestrate_node(state: GovernanceState) -> dict:
    # D46, cuttable: to remove this model call entirely, replace the body with
    #   return {"applicable_inspectors": list(INSPECTORS), "audit": ["orchestrate: fixed fan-out"]}
    if state.get("status") == "error":
        return {"audit": ["orchestrate skipped: upstream error"]}
    _stage(state, "orchestrating")
    out = agents.orchestrate_agent(state)
    picked = out["applicable_inspectors"]
    skipped = [i for i in INSPECTORS if i not in picked]
    _stage(state, "inspecting")  # last writer before the parallel superstep
    return {
        "applicable_inspectors": picked,
        "stage": "inspecting",
        "audit": [f"orchestrate done: {len(picked)} inspectors ({', '.join(picked)}); "
                  f"skipped {', '.join(skipped) or 'none'}. {out.get('why', '')}".strip()],
    }


# --- the five inspectors ----------------------------------------------------
# LangGraph runs every branch fanned out from one node in the SAME step, in
# parallel threads. Parallel writers may only touch reducer keys (findings_raw,
# inspector_reports, audit) or a key nobody else writes this step (risk_tier,
# written only by risk_assessment). None of them writes `stage`.


def _make_inspector_node(name: str):
    def node(state: GovernanceState) -> dict:
        return agents.INSPECTOR_AGENTS[name](state)

    node.__name__ = name
    return node


# --- fan-in merge (plain code, not an agent) --------------------------------


def inspector_status(reports: list, applicable: list) -> dict:
    """{"policy_compliance": "ok"|"failed"|"skipped", ...} - a failed inspector
    shows, a skipped-by-design one is honest about why it has no findings."""
    status = {name: ("failed" if name in applicable else "skipped") for name in INSPECTORS}
    for r in reports:
        if r.get("inspector") in status:
            status[r["inspector"]] = r.get("status", "failed")
    return status


def fan_in(state: GovernanceState) -> dict:
    if state.get("status") == "error":
        return {"audit": ["fan_in skipped: upstream error"]}
    _stage(state, "rolling_up")
    kept, dropped = [], 0
    for f in state["findings_raw"]:
        if isinstance(f, dict) and valid_finding(f):
            kept.append(f)
        else:
            dropped += 1  # half-formed findings are never shown
    tier = str(state.get("risk_tier", "")).lower()  # the casing trap, handled here
    checks = inspector_status(state["inspector_reports"], state.get("applicable_inspectors", []))
    asset = dict(state.get("asset", {}))
    asset["assessment"] = {
        "risk_tier": tier,
        "findings": kept,
        "risk": risk_rollup(kept),
        "inspector_status": checks,
    }
    return {
        "asset": asset,
        "risk_tier": tier,
        "risk": asset["assessment"]["risk"],
        "audit": [f"fan-in: {len(kept)} findings kept, {dropped} dropped, "
                  f"tier {tier or '?'}, checks {checks}"],
    }


def decide(state: GovernanceState) -> dict:
    # compliant vs flagged. NEVER auto-block (D31): a flag is a work item for a
    # human reviewer, not an automatic shutdown of someone's system.
    if state.get("status") == "error":
        return {"audit": ["decide skipped: upstream error"]}
    findings = (state.get("asset", {}).get("assessment") or {}).get("findings", [])
    verdict = "flagged" if findings else "compliant"
    asset = dict(state.get("asset", {}))
    asset["assessment"] = {**asset.get("assessment", {}), "decision": verdict}
    _stage(state, "done")
    return {
        "asset": asset,
        "decision": verdict,
        "status": "assessed",
        "stage": "done",
        "audit": [f"decision: {verdict} ({len(findings)} findings)"],
    }


# --- wiring -----------------------------------------------------------------


def after_orchestrate(state: GovernanceState):
    if state.get("status") == "error":
        return END
    return [i for i in state.get("applicable_inspectors", []) if i in INSPECTORS] or list(INSPECTORS)


builder = StateGraph(GovernanceState)
builder.add_node("inventory", guarded(inventory_node, "inventory"))
builder.add_node("orchestrate", guarded(orchestrate_node, "orchestrate"))
for _name in INSPECTORS:
    builder.add_node(_name, guarded(_make_inspector_node(_name), _name))
builder.add_node("fan_in", guarded(fan_in, "fan_in"))
builder.add_node("decide", guarded(decide, "decide"))

builder.add_edge(START, "inventory")
builder.add_edge("inventory", "orchestrate")
builder.add_conditional_edges("orchestrate", after_orchestrate, list(INSPECTORS) + [END])
for _name in INSPECTORS:
    builder.add_edge(_name, "fan_in")
builder.add_edge("fan_in", "decide")
builder.add_edge("decide", END)

graph = builder.compile()

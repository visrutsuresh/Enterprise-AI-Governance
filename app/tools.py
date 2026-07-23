"""The seven read-only tools the twelve agents share.

Agents differ mostly in which subset they are handed (the roster table in
the design spec, section 3). Everything here READS; no tool writes state.
run_tool swallows every exception into an "ERROR: ..." string the agent
reads as a normal observation, so a bad path degrades, never crashes.
All data access goes through packs.py / store.py / precedent.py, which are
anchored to their files, never the working directory (the 33a fix).
"""

from app import audit, packs, precedent, store

TOOLS = {}  # name -> function

REGISTRY_LIST_CAP = 50  # a full 185-asset dump would drown the model's context


def tool(fn):
    # Register a function so an agent can call it by name
    TOOLS[fn.__name__] = fn
    return fn


def run_tool(name: str, args: dict) -> str:
    # Dial a tool by name with its args; return the result as text
    fn = TOOLS.get(name)
    if fn is None:
        return f"ERROR: unknown tool {name!r}"
    try:
        return str(fn(**args))
    except Exception as e:
        return f"ERROR: {e}"


@tool
def registry_read(asset_id: str = "") -> dict | list:
    # One asset's full record, or (no id) a light list of the estate
    if asset_id:
        state = store.get(asset_id)
        if state is None:
            return {"error": f"no asset {asset_id!r} in the registry"}
        return state.get("asset", {})
    rows = store.list_all()
    light = [
        {"asset_id": r["asset_id"], "name": r["name"], "type": r["type"],
         "lifecycle": r["lifecycle"], "risk_tier": r["risk_tier"], "source": r["source"]}
        for r in rows[:REGISTRY_LIST_CAP]
    ]
    if len(rows) > REGISTRY_LIST_CAP:
        light.append({"note": f"{len(rows) - REGISTRY_LIST_CAP} more assets not shown"})
    return light


@tool
def policy_read() -> dict:
    # the active company policy pack, whole (it is small by design)
    return packs.load_policy_pack()


@tool
def framework_read() -> dict:
    # the active regulatory framework pack, whole
    return packs.load_framework_pack()


@tool
def precedent_search(query: str) -> list:
    # past governance decisions that read like the query, best match first
    return precedent.search(query)


@tool
def history_read(asset_id: str) -> dict:
    # what this asset was judged before: its stored assessment outcome
    state = store.get(asset_id)
    if state is None:
        return {"error": f"no asset {asset_id!r} in the registry"}
    return {
        "asset_id": asset_id,
        "status": state.get("status"),
        "risk_tier": state.get("risk_tier"),
        "risk": state.get("risk"),
        "decision": state.get("decision"),
        "findings": state.get("findings_raw", []),
    }


@tool
def audit_read(asset_id: str) -> dict:
    # the asset's hash-chained trail, with the tamper check already run
    state = store.get(asset_id)
    if state is None:
        return {"error": f"no asset {asset_id!r} in the registry"}
    log = state.get("audit") or []
    broken_at = audit.verify(log)
    return {"asset_id": asset_id, "entries": [e["step"] for e in log],
            "count": len(log), "intact": broken_at == -1}


@tool
def pack_read() -> dict:
    # which packs are live right now, in summary (the orchestrator's map)
    p, f = packs.load_policy_pack(), packs.load_framework_pack()
    return {
        "policy_pack": {"pack_id": p["pack_id"], "name": p.get("name", ""),
                        "rules": [{"id": r["id"], "title": r["title"]} for r in p["rules"]]},
        "framework_pack": {"pack_id": f["pack_id"], "name": f.get("name", ""),
                           "tiers": [{"tier": t["tier"], "rank": t["rank"]} for t in f["tiers"]]},
    }

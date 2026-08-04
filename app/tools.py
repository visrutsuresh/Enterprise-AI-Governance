"""The tools the twelve agents share: seven that READ, two that ACT.

Agents differ mostly in which subset they are handed (the roster table in
the design spec, section 3). The read tools come first; the WRITE tools are at
the bottom of the file behind their own rules.
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


# --- WRITE tools: the agents can now act, not only look -----------------------
#
# Everything above READS. Everything below CHANGES the estate, so it plays by
# stricter rules, carried over from #1's proven refund/cancellation pattern:
#
#   1. Every write appends to that asset's hash chain, attributed to the agent.
#   2. A write that assigns work to a named human is TWO-PHASE: the first call
#      returns a confirm code and changes nothing; only a call carrying the
#      matching code commits. The code is derived from the target id, so it is
#      recomputable and never stored.
#   3. Nothing here can block, delete, dismiss or approve. An agent proposes and
#      routes; a human still decides. That is the product promise, unchanged.

import hashlib

from app.state import ROUTING_TEAMS

_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O/1/I/L, so a human can read it aloud


def _confirm_code(target_id: str) -> str:
    # deterministic 5-char code per target; recomputable, so we verify without storing it
    digest = hashlib.sha256(target_id.encode()).digest()
    return "".join(_CODE_ALPHABET[b % len(_CODE_ALPHABET)] for b in digest[:5])


def _finding_on(asset_id: str, finding_id: str):
    state = store.get(asset_id)
    if state is None:
        return None, None
    for f in ((state.get("asset", {}).get("assessment") or {}).get("findings") or []):
        if f.get("finding_id") == finding_id:
            return state, f
    return state, None


def _commit(state: dict, entry: str) -> None:
    state["audit"] = audit.chain_as(state.get("audit") or [], [entry], by="agent")
    store.save(state)


@tool
def route_flag(asset_id: str, finding_id: str, team: str) -> dict:
    """Send a flag to the desk that owns it. Single-phase on purpose: routing is
    not destructive, it decides who reads something, and it never blocks anything."""
    team = str(team).strip().lower()
    if team not in ROUTING_TEAMS:
        return {"status": "error", "message": f"team must be one of: {', '.join(ROUTING_TEAMS)}"}
    state, finding = _finding_on(asset_id, finding_id)
    if state is None:
        return {"status": "error", "message": f"no asset {asset_id!r}"}
    if finding is None:
        return {"status": "error", "message": f"no finding {finding_id!r} on {asset_id}"}
    finding["routed_to"] = team
    _commit(state, f"agent_action route_flag: {finding_id} routed to {team}")
    return {"status": "routed", "finding_id": finding_id, "team": team}


@tool
def propose_remediation(asset_id: str, finding_id: str, owner: str, due_at: str, code: str = "") -> dict:
    """Put a named human on the hook with a deadline. Two-phase: the first call
    returns a code and changes nothing, a matching code commits."""
    state, finding = _finding_on(asset_id, finding_id)
    if state is None:
        return {"status": "error", "message": f"no asset {asset_id!r}"}
    if finding is None:
        return {"status": "error", "message": f"no finding {finding_id!r} on {asset_id}"}
    if (finding.get("status") or "open").lower() == "dismissed":
        return {"status": "error", "message": "that finding was dismissed by a reviewer; it takes no owner"}
    expected = _confirm_code(finding_id)
    if str(code).strip().upper() != expected:
        return {
            "status": "awaiting_confirmation",
            "confirm_code": expected,
            "message": f"Call again with code={expected} to assign {owner} a deadline of {due_at}.",
        }
    finding["owner"] = str(owner).strip() or None
    finding["due_at"] = str(due_at).strip() or None
    if (finding.get("status") or "open").lower() == "open":
        finding["status"] = "in_progress"
    _commit(state, f"agent_action propose_remediation: {finding_id} owner={finding['owner']} due={finding['due_at']}")
    return {"status": "assigned", "finding_id": finding_id, "owner": finding["owner"], "due_at": finding["due_at"]}

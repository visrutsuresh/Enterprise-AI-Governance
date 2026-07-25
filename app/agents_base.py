import json

from app import router, tools

MAX_STEPS = 6


def _parse(raw: str) -> dict:
    # the model sometimes emits a second JSON object or prose after its answer;
    # take the first complete object instead of slicing to the last brace
    obj, _ = json.JSONDecoder().raw_decode(raw[raw.find("{") :])
    return obj


def react(system: str, context: str, allowed_tools: list[str], max_steps: int = MAX_STEPS) -> dict:
    """Reason -> act -> observe loop. Returns the agent's finish result dict.
    Blocks repeated tool calls and forces a decision near the cap (#1 lessons)."""
    transcript, cache, redundant = "", {}, 0
    for step in range(max_steps):
        must_finish = redundant >= 2 or step >= max_steps - 1
        hint = "\nSTOP calling tools. Reply ONLY with the finish JSON." if must_finish else ""
        # 1024 default truncated multi-finding finish JSON mid-string; 4096 matches Papyrus
        move = _parse(router.think(f"{system}\n\n{context}\n{transcript}{hint}\nYour JSON:", max_new_tokens=4096))
        action = move.get("action")
        if action == "finish":
            return move.get("result", {})
        if action not in allowed_tools:
            transcript += f"\nunknown action {action!r}"
            continue
        args = move.get("args", {}) or {}
        key = f"{action}:{json.dumps(args, sort_keys=True)}"
        if key in cache:
            redundant += 1
            transcript += f"\n{action} already called; its result is above. Do not repeat it."
            continue
        obs = tools.run_tool(action, args)
        cache[key] = obs
        transcript += f"\n{action}({args}) -> {obs}"
    raise TimeoutError("agent hit the step cap without finishing")

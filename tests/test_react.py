import pytest

from app.agents_base import react


def test_react_blocks_repeat_calls_and_force_finishes(fake_model):
    calls = {"n": 0}

    def script(prompt):
        calls["n"] += 1
        if "STOP calling tools" in prompt:
            return {"action": "finish", "result": {"findings": []}}
        return {"action": "pack_read", "args": {}}  # repeats the same call forever

    fake_model(script)
    out = react("sys", "ctx", ["pack_read"])
    assert out == {"findings": []}
    assert calls["n"] <= 5  # blocked after 2 repeats, not allowed to burn the cap


def test_react_raises_at_step_cap(fake_model):
    fake_model(lambda prompt: {"action": "not_a_real_tool"})
    with pytest.raises(TimeoutError):
        react("sys", "ctx", ["pack_read"])


def test_react_rejects_unlisted_tool(fake_model):
    seen = []

    def script(prompt):
        seen.append(prompt)
        if len(seen) == 1:
            return {"action": "registry_read", "args": {}}  # not on this agent's list
        return {"action": "finish", "result": {"ok": True}}

    fake_model(script)
    assert react("sys", "ctx", ["pack_read"]) == {"ok": True}
    assert "unknown action 'registry_read'" in seen[1]  # the refusal is shown to the model

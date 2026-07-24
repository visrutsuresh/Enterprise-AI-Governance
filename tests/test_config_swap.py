"""NFR-1 guarded by a test: the SAME asset yields DIFFERENT flags when the
policy pack env var changes, with zero code change.

The fake model here is an obedient inspector: it calls policy_read and flags
the first rule id it sees in the observation. So if the env var truly reaches
the loader, the tool, and the prompt, acme and globex produce different
control_ids. If any link hardcodes a pack, this test fails.
"""

import re

from app.agents import policy_compliance_agent

STATE = {
    "asset_id": "AI-swap1",
    "asset": {
        "asset_id": "AI-swap1", "type": "agent", "name": "Swap Probe", "owner": "t",
        "purpose": "t", "lifecycle": "production", "deployment": "cloud",
        "data_touched": ["customer PII"], "third_party": "OpenAI API", "human_oversight": "",
    },
}


def obedient_inspector(prompt):
    if "policy_read({})" not in prompt:
        return {"action": "policy_read", "args": {}}
    rule_id = re.search(r"'(POL|GLX)-\d+'", prompt).group(0).strip("'")
    return {"action": "finish", "result": {"findings": [{
        "control_id": rule_id, "severity": "high",
        "plain": "The first rule in the live pack fires on this asset.",
        "evidence": "as observed in policy_read",
        "remediation": "Fix it.",
    }]}}


def _flags_under(pack: str, monkeypatch, fake_model) -> set:
    monkeypatch.setenv("POLICY_PACK", pack)
    fake_model(obedient_inspector)
    update = policy_compliance_agent(dict(STATE))
    return {f["control_id"] for f in update["findings_raw"]}


def test_same_asset_different_packs_different_flags(monkeypatch, fake_model):
    acme_flags = _flags_under("acme", monkeypatch, fake_model)
    globex_flags = _flags_under("globex", monkeypatch, fake_model)
    assert acme_flags == {"POL-01"}
    assert globex_flags == {"GLX-01"}
    assert acme_flags != globex_flags  # the pack swap changed the outcome, no code changed

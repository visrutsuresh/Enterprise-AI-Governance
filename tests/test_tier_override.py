"""Human override of the AI-assigned risk tier.

The model mis-tiers roughly 1 in 4 assets; the correction path must exist,
demand a reason, and land on the tamper-evident chain.

Driven through the real endpoint with the database swapped for a dict. $0, no model.
"""

import pytest
from fastapi.testclient import TestClient

import api as api_mod
from app import audit
from app.users import require_reviewer


class FakeUser:
    email = "reviewer@example.com"
    role = "reviewer"


@pytest.fixture
def client(monkeypatch):
    state = {
        "asset_id": "AI-0042",
        "status": "assessed",
        "risk_tier": "limited",
        "audit": audit.chain([], ["inventory: registered", "decide: assessed"]),
    }
    saved = {}
    monkeypatch.setattr(api_mod.store, "get", lambda asset_id: state if asset_id == "AI-0042" else None)
    monkeypatch.setattr(api_mod.store, "save", lambda s: saved.update(state=s))
    api_mod.app.dependency_overrides[require_reviewer] = lambda: FakeUser()
    c = TestClient(api_mod.app)
    c.state, c.saved = state, saved
    yield c
    api_mod.app.dependency_overrides.clear()


def test_override_changes_tier_and_lands_on_the_chain(client):
    r = client.post("/assets/AI-0042/tier", json={"tier": "High", "reason": "reads biometric data, the model missed it"})
    assert r.status_code == 200
    assert client.state["risk_tier"] == "high"  # casing normalised at the door
    assert client.state["tier_override"]["from"] == "limited"
    assert client.state["tier_override"]["by"] == "reviewer@example.com"
    assert any("tier_override" in e["step"] for e in client.state["audit"])
    assert audit.verify(client.state["audit"]) == -1  # chain intact
    assert client.saved  # persisted, not just mutated in memory


def test_override_without_reason_is_refused(client):
    r = client.post("/assets/AI-0042/tier", json={"tier": "high", "reason": "  "})
    assert r.status_code == 422
    assert client.state["risk_tier"] == "limited"


def test_unknown_tier_is_refused(client):
    r = client.post("/assets/AI-0042/tier", json={"tier": "catastrophic", "reason": "x"})
    assert r.status_code == 422


def test_same_tier_conflicts(client):
    r = client.post("/assets/AI-0042/tier", json={"tier": "limited", "reason": "no change"})
    assert r.status_code == 409


def test_missing_asset_404s(client):
    r = client.post("/assets/AI-9999/tier", json={"tier": "high", "reason": "x"})
    assert r.status_code == 404

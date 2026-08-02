"""Reviewer verdicts on flags.

Routing says who should look. These pin what the reviewer CONCLUDED, which is the
half an auditor asks about: not "was it flagged" but "who dismissed it, and why".

Driven through the real endpoint with the database swapped for a dict. $0, no model.
"""

import pytest
from conftest import make_finding
from fastapi.testclient import TestClient

import api as api_mod
from app import audit
from app.users import require_reviewer


class FakeUser:
    email = "reviewer@example.com"
    role = "reviewer"


@pytest.fixture
def client(monkeypatch):
    """One asset holding one open finding, stored in a dict instead of Postgres."""
    state = {
        "asset_id": "AI-0042",
        "status": "flagged",
        "audit": audit.chain([], ["inventory: registered", "decide: flagged"]),
        "asset": {"asset_id": "AI-0042", "assessment": {"findings": [make_finding(finding_id="f-AI-0042-pol-1")]}},
    }
    saved = {}
    monkeypatch.setattr(api_mod.store, "get", lambda asset_id: state if asset_id == "AI-0042" else None)
    monkeypatch.setattr(api_mod.store, "save", lambda s: saved.update(state=s))

    api_mod.app.dependency_overrides[require_reviewer] = lambda: FakeUser()
    c = TestClient(api_mod.app)
    c.state, c.saved = state, saved  # the test reads these back
    yield c
    api_mod.app.dependency_overrides.clear()


def finding(client):
    return client.state["asset"]["assessment"]["findings"][0]


def test_approve_confirms_the_finding_and_leaves_the_work_open(client):
    r = client.post("/flags/f-AI-0042-pol-1/decision", json={"verdict": "approved"})
    assert r.status_code == 200
    f = finding(client)
    assert f["review"]["verdict"] == "approved"
    assert f["review"]["by"] == "reviewer@example.com"
    # confirmed means the remediation still has to happen, so it must NOT drop out of the open count
    assert f["status"] == "open"


def test_override_dismisses_the_finding_and_keeps_the_reason(client):
    r = client.post(
        "/flags/f-AI-0042-pol-1/decision",
        json={"verdict": "overridden", "reason": "the vendor is inside our own tenancy"},
    )
    assert r.status_code == 200
    f = finding(client)
    assert f["status"] == "dismissed"
    assert f["review"]["reason"] == "the vendor is inside our own tenancy"


def test_override_without_a_reason_is_refused(client):
    r = client.post("/flags/f-AI-0042-pol-1/decision", json={"verdict": "overridden", "reason": "   "})
    assert r.status_code == 422
    assert "reason" in r.json()["detail"]
    assert "review" not in finding(client)  # nothing recorded on a refused call


def test_an_unknown_verdict_is_refused(client):
    r = client.post("/flags/f-AI-0042-pol-1/decision", json={"verdict": "ignored"})
    assert r.status_code == 422


def test_a_flag_cannot_be_decided_twice(client):
    assert client.post("/flags/f-AI-0042-pol-1/decision", json={"verdict": "approved"}).status_code == 200
    again = client.post("/flags/f-AI-0042-pol-1/decision", json={"verdict": "overridden", "reason": "changed my mind"})
    assert again.status_code == 409
    assert finding(client)["review"]["verdict"] == "approved"  # the first verdict stands


def test_unknown_finding_and_unknown_asset_both_404(client):
    assert client.post("/flags/f-AI-0042-pol-9/decision", json={"verdict": "approved"}).status_code == 404
    assert client.post("/flags/f-AI-9999-pol-1/decision", json={"verdict": "approved"}).status_code == 404


def test_the_verdict_joins_the_audit_chain_and_the_chain_stays_intact(client):
    before = len(client.state["audit"])
    client.post(
        "/flags/f-AI-0042-pol-1/decision",
        json={"verdict": "overridden", "reason": "compensating control in place"},
    )
    chain = client.state["audit"]
    assert len(chain) == before + 1
    assert audit.verify(chain) == -1  # the new entry links to the one before it
    step = chain[-1]["step"]
    assert "overridden" in step and "compensating control in place" in step and "reviewer@example.com" in step


def test_the_decision_is_persisted_not_just_held_in_memory(client):
    client.post("/flags/f-AI-0042-pol-1/decision", json={"verdict": "approved"})
    assert client.saved["state"]["asset"]["assessment"]["findings"][0]["review"]["verdict"] == "approved"


def test_owner_cannot_decide_their_own_finding(client):
    # maker-checker: the person doing the remediation must not be the person signing it off
    finding(client)["owner"] = "reviewer@example.com"
    r = client.post("/flags/f-AI-0042-pol-1/decision", json={"verdict": "approved"})
    assert r.status_code == 403
    assert finding(client).get("review") is None

"""Issues a HUMAN found, not an agent.

Until POST /assets/{id}/findings existed, every finding on the estate was minted
by an inspector, so a pen-test result, an incident, or something raised in a
meeting could not be recorded at all. These pin the four things that make a
hand-logged issue trustworthy: it is attributed, it is on the hash chain, it
survives a pack re-score, and the person who raised it cannot also sign it off.
$0, no model, no Modal.
"""

import pytest
from fastapi.testclient import TestClient

import api as api_mod
from app import audit, sweep
from app.users import require_reviewer

RAISER = "lucy.reviewer@governance.test"


class FakeUser:
    email = RAISER
    role = "reviewer"


@pytest.fixture
def client(monkeypatch):
    """One registered asset with no findings, stored in a dict instead of Postgres."""
    state = {
        "asset_id": "AI-0042",
        "status": "assessed",
        "audit": audit.chain([], ["inventory: registered"]),
        "asset": {
            "asset_id": "AI-0042",
            "name": "ClaimTriage",
            "type": "model",
            "lifecycle": "production",
            "owner": "claims-ops",
            "assessment": {"findings": []},
        },
    }
    monkeypatch.setattr(api_mod.store, "get", lambda asset_id: state if asset_id == "AI-0042" else None)
    monkeypatch.setattr(api_mod.store, "save", lambda s: None)

    api_mod.app.dependency_overrides[require_reviewer] = lambda: FakeUser()
    c = TestClient(api_mod.app)
    c.state = state
    yield c
    api_mod.app.dependency_overrides.clear()


def findings(client):
    return client.state["asset"]["assessment"]["findings"]


def test_a_person_can_log_an_issue_and_it_is_attributed_to_them(client):
    r = client.post("/assets/AI-0042/findings", json={
        "plain": "Pen test found the API returns PII without auth",
        "severity": "high",
        "evidence": "Red-team report RT-2026-08",
    })
    assert r.status_code == 200
    body = r.json()
    assert body["inspector"] == "human"  # not an inspector name, so it is never mistaken for agent output
    assert body["severity"] == "high"
    assert findings(client)[0]["raised_by"] == RAISER


def test_logging_an_issue_joins_the_audit_chain(client):
    before = len(client.state["audit"])
    client.post("/assets/AI-0042/findings", json={"plain": "Recruiters override the score silently"})
    log = client.state["audit"]
    assert len(log) == before + 1
    assert audit.verify(log) == -1  # the chain still holds
    assert log[-1]["by"] == RAISER
    assert "finding_logged" in log[-1]["step"]


def test_an_untitled_issue_is_refused(client):
    r = client.post("/assets/AI-0042/findings", json={"plain": "   "})
    assert r.status_code == 422


def test_a_bad_severity_is_refused_by_name(client):
    r = client.post("/assets/AI-0042/findings", json={"plain": "x", "severity": "catastrophic"})
    assert r.status_code == 422
    assert "severity" in r.json()["detail"]


def test_assigning_without_a_date_gets_the_sla_deadline(client):
    # a tracker where every deadline must be hand-typed is a spreadsheet
    r = client.post("/assets/AI-0042/findings", json={
        "plain": "x", "severity": "high", "owner": "omar@governance.test",
    })
    assert r.json()["due_at"] is not None  # high = 7 days, set for them


def test_ids_do_not_collide_with_a_second_logged_issue(client):
    a = client.post("/assets/AI-0042/findings", json={"plain": "first"}).json()
    b = client.post("/assets/AI-0042/findings", json={"plain": "second"}).json()
    assert a["finding_id"] != b["finding_id"]


def test_the_raiser_cannot_decide_their_own_finding(client, monkeypatch):
    """maker-checker: the segregation of duties has to survive the new path in."""
    created = client.post("/assets/AI-0042/findings", json={"plain": "x"}).json()
    fid = created["finding_id"]
    monkeypatch.setattr(
        api_mod, "_find_finding",
        lambda _fid: (client.state, client.state["asset"]["assessment"], findings(client)[0]),
    )
    r = client.post(f"/flags/{fid}/decision", json={"verdict": "approved"})
    assert r.status_code == 403
    assert "logged this finding" in r.json()["detail"]


def test_a_logged_issue_survives_a_policy_rescore(client, monkeypatch):
    """The one that would quietly lose a human's work. rescore_one replaces the
    POLICY findings; anything raised by a person must be left alone."""
    client.post("/assets/AI-0042/findings", json={"plain": "Raised in the hiring review"})
    # an empty pack: every policy finding should be dropped, so if the human one
    # is also dropped the test fails for exactly the right reason
    monkeypatch.setattr(sweep.packs, "load_policy_pack",
                        lambda name=None: {"pack_id": "empty-v1", "rules": []})
    sweep.rescore_one(client.state)
    kept = findings(client)
    assert len(kept) == 1 and kept[0]["inspector"] == "human"

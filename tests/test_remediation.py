"""The remediation board: owner, deadline, and a state that moves.

Routing says who should look. A decision says what they concluded. These pin the
missing middle, which is whether the work actually got DONE and whether that
progress is provable. Driven through the real endpoints with the database swapped
for a dict. $0, no model, no Modal.
"""

import pytest
from conftest import make_finding
from fastapi.testclient import TestClient

import api as api_mod
from app import audit
from app.users import require_reviewer

REVIEWER = "lucy.reviewer@governance.test"
OTHER = "omar.reviewer@governance.test"


class FakeUser:
    email = REVIEWER
    role = "reviewer"


def row(finding, asset_id="AI-0042", name="ClaimTriage", tier="high"):
    """One row in the shape store.list_findings returns: asset context + finding."""
    return {
        "asset_id": asset_id,
        "asset_name": name,
        "risk_tier": tier,
        "risk_level": "serious",
        "asset_owner": "claims-ops",
        "created_at": None,
        "finding": finding,
    }


@pytest.fixture
def client(monkeypatch):
    """One asset holding one open finding, stored in a dict instead of Postgres."""
    state = {
        "asset_id": "AI-0042",
        "status": "flagged",
        "audit": audit.chain([], ["inventory: registered", "decide: flagged"]),
        "asset": {
            "asset_id": "AI-0042",
            "name": "ClaimTriage",
            "risk_tier": "high",
            "assessment": {"findings": [make_finding(finding_id="f-AI-0042-pol-1")]},
        },
    }
    saved = {}
    monkeypatch.setattr(api_mod.store, "get", lambda asset_id: state if asset_id == "AI-0042" else None)
    monkeypatch.setattr(api_mod.store, "save", lambda s: saved.update(state=s))

    api_mod.app.dependency_overrides[require_reviewer] = lambda: FakeUser()
    c = TestClient(api_mod.app)
    c.state, c.saved = state, saved
    yield c
    api_mod.app.dependency_overrides.clear()


def finding(client):
    return client.state["asset"]["assessment"]["findings"][0]


def board(monkeypatch, rows):
    monkeypatch.setattr(api_mod.store, "list_findings", lambda: rows)


# --- GET /remediation --------------------------------------------------------


def test_the_board_returns_findings_with_their_asset_context(client, monkeypatch):
    board(monkeypatch, [row(make_finding(finding_id="f-AI-0042-pol-1"))])
    r = client.get("/remediation")
    assert r.status_code == 200
    body = r.json()
    f = body["findings"][0]
    # the asset name and tier matter: a finding with no asset is unactionable
    assert f["asset_name"] == "ClaimTriage" and f["risk_tier"] == "high"
    assert f["status"] == "open" and f["owner"] is None
    assert body["counts"]["open"] == 1


def test_a_finding_with_no_id_is_left_off_the_board(client, monkeypatch):
    # fan_in already logs malformed findings; they simply cannot be worked on
    board(monkeypatch, [row(make_finding(finding_id=None)), row(make_finding(finding_id="f-AI-0042-pol-2"))])
    assert len(client.get("/remediation").json()["findings"]) == 1


def test_the_mine_filter_matches_on_owner(client, monkeypatch):
    board(monkeypatch, [
        row(make_finding(finding_id="f-AI-0042-pol-1", owner=REVIEWER)),
        row(make_finding(finding_id="f-AI-0042-pol-2", owner=OTHER)),
    ])
    got = client.get("/remediation?mine=true").json()["findings"]
    assert [f["finding_id"] for f in got] == ["f-AI-0042-pol-1"]


def test_the_unassigned_filter_finds_work_nobody_owns(client, monkeypatch):
    board(monkeypatch, [
        row(make_finding(finding_id="f-AI-0042-pol-1", owner=REVIEWER)),
        row(make_finding(finding_id="f-AI-0042-pol-2")),
    ])
    got = client.get("/remediation?unassigned=true").json()["findings"]
    assert [f["finding_id"] for f in got] == ["f-AI-0042-pol-2"]


def test_overdue_means_past_due_and_still_being_worked_on(client, monkeypatch):
    board(monkeypatch, [
        row(make_finding(finding_id="f-late", due_at="2020-01-01", status="in_progress")),
        row(make_finding(finding_id="f-future", due_at="2099-01-01", status="in_progress")),
        # closed work is not overdue however late it was: the job is done
        row(make_finding(finding_id="f-done", due_at="2020-01-01", status="closed")),
        row(make_finding(finding_id="f-none", status="open")),
    ])
    body = client.get("/remediation?overdue=true").json()
    assert [f["finding_id"] for f in body["findings"]] == ["f-late"]
    assert body["overdue"] == 1


def test_an_unparseable_due_date_is_not_treated_as_overdue(client, monkeypatch):
    # bad data is a data problem; it must not silently manufacture urgency
    board(monkeypatch, [row(make_finding(finding_id="f-bad", due_at="whenever", status="open"))])
    assert client.get("/remediation?overdue=true").json()["findings"] == []


def test_the_status_filter_works_and_a_bad_status_is_refused(client, monkeypatch):
    board(monkeypatch, [
        row(make_finding(finding_id="f-a", status="open")),
        row(make_finding(finding_id="f-b", status="closed")),
    ])
    got = client.get("/remediation?status=closed").json()["findings"]
    assert [f["finding_id"] for f in got] == ["f-b"]
    assert client.get("/remediation?status=finished").status_code == 422


def test_the_team_filter_reuses_the_routing_field(client, monkeypatch):
    board(monkeypatch, [
        row(make_finding(finding_id="f-a", routed_to="Legal")),
        row(make_finding(finding_id="f-b", routed_to="Platform")),
    ])
    got = client.get("/remediation?team=Legal").json()["findings"]
    assert [f["finding_id"] for f in got] == ["f-a"]


# --- PATCH /flags/{id} -------------------------------------------------------


def test_assigning_an_owner_and_a_deadline_and_moving_the_card(client):
    r = client.patch("/flags/f-AI-0042-pol-1",
                     json={"owner": OTHER, "due_at": "2026-08-05", "status": "in_progress"})
    assert r.status_code == 200
    f = finding(client)
    assert f["owner"] == OTHER and f["due_at"] == "2026-08-05" and f["status"] == "in_progress"
    assert r.json()["status"] == "in_progress"


def test_an_owner_can_be_cleared_back_to_unassigned(client):
    client.patch("/flags/f-AI-0042-pol-1", json={"owner": OTHER})
    # an explicit null must mean "unassign", not "leave it alone"
    assert client.patch("/flags/f-AI-0042-pol-1", json={"owner": None}).status_code == 200
    assert finding(client)["owner"] is None


def test_a_status_outside_the_board_columns_is_refused(client):
    r = client.patch("/flags/f-AI-0042-pol-1", json={"status": "nearly_done"})
    assert r.status_code == 422
    assert finding(client)["status"] == "open"  # nothing changed on a refused call


def test_a_finding_cannot_be_dismissed_by_dragging(client):
    # dismissing needs a written reason, so it stays on the override path
    r = client.patch("/flags/f-AI-0042-pol-1", json={"status": "dismissed"})
    assert r.status_code == 422
    assert "override" in r.json()["detail"]
    assert finding(client)["status"] == "open"


def test_a_dismissed_finding_cannot_be_revived(client):
    client.post("/flags/f-AI-0042-pol-1/decision",
                json={"verdict": "overridden", "reason": "compensating control in place"})
    r = client.patch("/flags/f-AI-0042-pol-1", json={"status": "in_progress"})
    assert r.status_code == 409
    assert finding(client)["status"] == "dismissed"  # the recorded judgement stands


def test_a_bad_due_date_is_refused(client):
    assert client.patch("/flags/f-AI-0042-pol-1", json={"due_at": "next tuesday"}).status_code == 422


def test_an_empty_patch_is_refused(client):
    assert client.patch("/flags/f-AI-0042-pol-1", json={}).status_code == 422


def test_unknown_finding_and_unknown_asset_both_404(client):
    assert client.patch("/flags/f-AI-0042-pol-9", json={"status": "closed"}).status_code == 404
    assert client.patch("/flags/f-AI-9999-pol-1", json={"status": "closed"}).status_code == 404


def test_every_remediation_change_joins_the_audit_chain_intact(client):
    before = len(client.state["audit"])
    client.patch("/flags/f-AI-0042-pol-1", json={"owner": OTHER, "status": "in_progress"})
    chain = client.state["audit"]
    assert len(chain) == before + 1
    assert audit.verify(chain) == -1  # the new entry links to the one before it
    step = chain[-1]["step"]
    assert "in_progress" in step and OTHER in step and REVIEWER in step


def test_the_change_is_persisted_not_just_held_in_memory(client):
    client.patch("/flags/f-AI-0042-pol-1", json={"status": "closed"})
    assert client.saved["state"]["asset"]["assessment"]["findings"][0]["status"] == "closed"


def test_an_approved_finding_stays_open_and_therefore_stays_on_the_board(client, monkeypatch):
    # approve confirms the finding; the remediation work still has to happen, so it
    # must be exactly what the board shows as waiting to be picked up
    client.post("/flags/f-AI-0042-pol-1/decision", json={"verdict": "approved"})
    board(monkeypatch, [row(finding(client))])
    got = client.get("/remediation?status=open").json()["findings"]
    assert [f["finding_id"] for f in got] == ["f-AI-0042-pol-1"]
    assert got[0]["review"]["verdict"] == "approved"

"""The WRITE tools: the moment the agents stopped being advisors.

Every tool before these READ. These change the estate, so they carry stricter
rules and every one of them is pinned here: the two-phase confirm, the hash
chain entry, the refusals, and the promise that an agent still cannot block,
dismiss or approve anything. $0, no model, no Modal.
"""

import pytest
from conftest import make_finding

from app import audit, store, tools


@pytest.fixture
def estate(monkeypatch):
    """One asset with one finding, held in a dict instead of Postgres."""
    state = {
        "asset_id": "AI-0042",
        "status": "assessed",
        "asset": {
            "asset_id": "AI-0042",
            "name": "ClaimTriage",
            "owner": "claims-ops",
            "assessment": {"findings": [make_finding()]},
        },
        "audit": audit.chain([], ["decision: flagged (1 findings)"]),
    }
    db = {"AI-0042": state}
    monkeypatch.setattr(store, "get", lambda aid: db.get(aid))
    monkeypatch.setattr(store, "save", lambda s: db.__setitem__(s["asset_id"], s))
    return db


def finding_of(db):
    return db["AI-0042"]["asset"]["assessment"]["findings"][0]


# --- route_flag: single-phase, because routing decides who reads, not what happens ---


def test_route_flag_really_writes_the_desk(estate):
    out = tools.route_flag("AI-0042", "f-AI-0001-pol-1", "legal")
    assert out["status"] == "routed"
    assert finding_of(estate)["routed_to"] == "legal"


def test_route_flag_lands_on_the_chain_and_leaves_it_intact(estate):
    before = len(estate["AI-0042"]["audit"])
    tools.route_flag("AI-0042", "f-AI-0001-pol-1", "security")
    log = estate["AI-0042"]["audit"]
    assert len(log) == before + 1
    assert audit.verify(log) == -1
    assert "agent_action route_flag" in log[-1]["step"]
    assert log[-1]["by"] == "agent"  # attributed to the machine, never to a person


def test_route_flag_refuses_a_desk_that_does_not_exist(estate):
    out = tools.route_flag("AI-0042", "f-AI-0001-pol-1", "marketing")
    assert out["status"] == "error"
    assert finding_of(estate).get("routed_to") is None


def test_route_flag_on_an_unknown_asset_or_finding_is_an_error_not_a_crash(estate):
    assert tools.route_flag("AI-9999", "f-AI-0001-pol-1", "legal")["status"] == "error"
    assert tools.route_flag("AI-0042", "f-nope-1", "legal")["status"] == "error"


# --- propose_remediation: two-phase, because it puts a human on the hook ---


def test_first_call_changes_nothing_and_returns_a_code(estate):
    out = tools.propose_remediation("AI-0042", "f-AI-0001-pol-1", "priya", "2026-08-18")
    assert out["status"] == "awaiting_confirmation"
    assert len(out["confirm_code"]) == 5
    f = finding_of(estate)
    assert f.get("owner") is None and f.get("due_at") is None
    assert f["status"] == "open"


def test_a_matching_code_commits_the_assignment(estate):
    code = tools.propose_remediation("AI-0042", "f-AI-0001-pol-1", "priya", "2026-08-18")["confirm_code"]
    out = tools.propose_remediation("AI-0042", "f-AI-0001-pol-1", "priya", "2026-08-18", code=code)
    assert out["status"] == "assigned"
    f = finding_of(estate)
    assert f["owner"] == "priya"
    assert f["due_at"] == "2026-08-18"
    assert f["status"] == "in_progress"  # open work that now has an owner is in progress


def test_a_wrong_code_never_commits(estate):
    out = tools.propose_remediation("AI-0042", "f-AI-0001-pol-1", "priya", "2026-08-18", code="ZZZZZ")
    assert out["status"] == "awaiting_confirmation"
    assert finding_of(estate).get("owner") is None


def test_the_code_is_recomputable_and_specific_to_the_finding():
    assert tools._confirm_code("f-a") == tools._confirm_code("f-a")
    assert tools._confirm_code("f-a") != tools._confirm_code("f-b")


def test_only_the_committed_call_touches_the_chain(estate):
    before = len(estate["AI-0042"]["audit"])
    tools.propose_remediation("AI-0042", "f-AI-0001-pol-1", "priya", "2026-08-18")
    assert len(estate["AI-0042"]["audit"]) == before  # the offer wrote nothing
    code = tools._confirm_code("f-AI-0001-pol-1")
    tools.propose_remediation("AI-0042", "f-AI-0001-pol-1", "priya", "2026-08-18", code=code)
    log = estate["AI-0042"]["audit"]
    assert len(log) == before + 1
    assert audit.verify(log) == -1


def test_an_agent_cannot_assign_work_on_a_dismissed_finding(estate):
    finding_of(estate)["status"] = "dismissed"
    code = tools._confirm_code("f-AI-0001-pol-1")
    out = tools.propose_remediation("AI-0042", "f-AI-0001-pol-1", "priya", "2026-08-18", code=code)
    assert out["status"] == "error"
    assert finding_of(estate).get("owner") is None


def test_a_committed_assignment_does_not_overwrite_a_reviewers_progress(estate):
    finding_of(estate)["status"] = "awaiting_evidence"
    code = tools._confirm_code("f-AI-0001-pol-1")
    tools.propose_remediation("AI-0042", "f-AI-0001-pol-1", "priya", "2026-08-18", code=code)
    # only an untouched 'open' finding is advanced; a human's later state stands
    assert finding_of(estate)["status"] == "awaiting_evidence"


# --- the promise that survived: an agent proposes, a human decides ---


def test_no_write_tool_can_approve_dismiss_or_block(estate):
    """The registry is the contract. If a future tool named like a verdict shows
    up here, that is a product decision and it should fail this test first."""
    forbidden = ("approve", "dismiss", "block", "delete", "resolve", "close")
    acting = [n for n in tools.TOOLS if any(w in n for w in forbidden)]
    assert acting == []

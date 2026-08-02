"""The sweep runs in the background and the tower polls its status.

TestClient executes background tasks after the response, which is exactly
what lets us assert the full started -> done arc. $0, no model.
"""

import pytest
from fastapi.testclient import TestClient

import api as api_mod
from app import ratelimit
from app.users import require_admin, require_reviewer


class FakeAdmin:
    email = "admin@example.com"
    role = "admin"


@pytest.fixture
def client(monkeypatch):
    ratelimit._hits.clear()  # the limiter is module state; tests must not inherit spent budgets
    api_mod._SWEEP_STATE.clear()
    api_mod._SWEEP_STATE["state"] = "idle"
    monkeypatch.setattr(api_mod.sweep, "run_sweep",
                        lambda limit: {"report": "all clear", "monitored": limit, "new_findings": 0, "not_swept": 0})
    api_mod.app.dependency_overrides[require_admin] = lambda: FakeAdmin()
    api_mod.app.dependency_overrides[require_reviewer] = lambda: FakeAdmin()
    c = TestClient(api_mod.app)
    yield c
    api_mod.app.dependency_overrides.clear()


def test_sweep_starts_then_status_reports_done(client):
    r = client.post("/sweep/run", json={"limit": 5})
    assert r.status_code == 200
    assert r.json()["state"] == "started"
    s = client.get("/sweep/status").json()
    assert s["state"] == "done"
    assert s["report"]["monitored"] == 5


def test_sweep_error_is_visible_not_silent(client, monkeypatch):
    def boom(limit):
        raise RuntimeError("lane down")
    monkeypatch.setattr(api_mod.sweep, "run_sweep", boom)
    client.post("/sweep/run", json={"limit": 5})
    s = client.get("/sweep/status").json()
    assert s["state"] == "error"
    assert "lane down" in s["error"]


def test_second_sweep_while_running_conflicts(client):
    api_mod._SWEEP_STATE["state"] = "running"
    assert client.post("/sweep/run", json={"limit": 5}).status_code == 409

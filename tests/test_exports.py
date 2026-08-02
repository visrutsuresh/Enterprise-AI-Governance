"""CSV exports: the artifact you hand an external auditor.

Real endpoints, database swapped for dicts. $0, no model.
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
    chain = audit.chain([], ["inventory: registered", "decide: flagged"])
    monkeypatch.setattr(api_mod.store, "list_all", lambda: [
        {"asset_id": "AI-0001", "name": "Churn, Model", "type": "model", "owner": "ops",
         "lifecycle": "production", "status": "flagged", "risk_tier": "high",
         "risk_level": "high", "source": "seed", "created_at": "2026-08-01", "open_findings": 2},
    ])
    monkeypatch.setattr(api_mod.store, "list_findings", lambda: [
        {"asset_id": "AI-0001", "asset_name": "Churn, Model", "risk_tier": "high",
         "finding": make_finding(review={"verdict": "approved", "by": "r@x.com", "at": "t", "reason": ""})},
    ])
    monkeypatch.setattr(api_mod.store, "get",
                        lambda asset_id: {"asset_id": "AI-0001", "audit": chain} if asset_id == "AI-0001" else None)
    api_mod.app.dependency_overrides[require_reviewer] = lambda: FakeUser()
    c = TestClient(api_mod.app)
    yield c
    api_mod.app.dependency_overrides.clear()


def test_register_csv_has_header_and_row(client):
    r = client.get("/export/register.csv")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("asset_id,name,")
    assert len(lines) == 2
    assert '"Churn, Model"' in lines[1]  # commas in names must not break columns


def test_findings_csv_flattens_review(client):
    r = client.get("/export/findings.csv")
    assert r.status_code == 200
    lines = r.text.strip().splitlines()
    assert "review_verdict" in lines[0]
    assert "approved" in lines[1]


def test_audit_csv_marks_intact_entries(client):
    r = client.get("/assets/AI-0001/audit.csv")
    assert r.status_code == 200
    lines = r.text.strip().splitlines()
    assert len(lines) == 3  # header + 2 entries
    assert lines[1].endswith("True")


def test_audit_csv_404_on_missing_asset(client):
    assert client.get("/assets/AI-9999/audit.csv").status_code == 404

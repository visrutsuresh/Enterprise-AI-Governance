"""Evidence attached to a finding.

The board has always had an AWAITING EVIDENCE column. These pin the thing that
column was waiting for: a file somebody produced to prove the remediation
happened, inspectable later by an auditor, and recorded in the asset's chain
like every other change to a finding.

Driven through the real endpoints with the database swapped for dicts. $0, no model.
"""

from datetime import datetime, timezone

import pytest
from conftest import make_finding
from fastapi.testclient import TestClient

import api as api_mod
from app import audit
from app.users import require_reviewer


class FakeUser:
    email = "[REDACTED_EMAIL_ADDRESS_4]"
    role = "reviewer"


@pytest.fixture
def client(monkeypatch):
    """One asset, one open finding, and an in-memory stand-in for the evidence table."""
    state = {
        "asset_id": "AI-0042",
        "status": "flagged",
        "audit": audit.chain([], ["inventory: registered", "decide: flagged"]),
        "asset": {
            "asset_id": "AI-0042",
            "assessment": {"findings": [make_finding(finding_id="f-AI-0042-pol-1")]},
        },
    }
    table: list[dict] = []

    def add_evidence(finding_id, asset_id, filename, content_type, data, uploaded_by):
        row = {
            "id": len(table) + 1,
            "finding_id": finding_id,
            "asset_id": asset_id,
            "filename": filename,
            "content_type": content_type,
            "size": len(data),
            "data": data,
            "uploaded_by": uploaded_by,
            "created_at": datetime.now(timezone.utc),
        }
        table.append(row)
        return row

    monkeypatch.setattr(api_mod.store, "get", lambda asset_id: state if asset_id == "AI-0042" else None)
    monkeypatch.setattr(api_mod.store, "save", lambda s: None)
    monkeypatch.setattr(api_mod.store, "add_evidence", add_evidence)
    def list_evidence(finding_id):
        # mirrors the real SELECT, which never opens the bytes column
        cols = ("id", "finding_id", "asset_id", "filename", "content_type", "size", "uploaded_by", "created_at")
        return [{k: r[k] for k in cols} for r in table if r["finding_id"] == finding_id]

    monkeypatch.setattr(api_mod.store, "list_evidence", list_evidence)
    monkeypatch.setattr(
        api_mod.store, "get_evidence", lambda eid: next((r for r in table if r["id"] == eid), None)
    )

    api_mod.app.dependency_overrides[require_reviewer] = lambda: FakeUser()
    c = TestClient(api_mod.app)
    c.state, c.table = state, table
    yield c
    api_mod.app.dependency_overrides.clear()


def finding(client):
    return client.state["asset"]["assessment"]["findings"][0]


def png(name="proof.png", body=b"\x89PNG fake bytes"):
    return {"file": (name, body, "image/png")}


def test_upload_stores_the_file_and_mirrors_it_onto_the_finding(client):
    r = client.post("/flags/f-AI-0042-pol-1/evidence", files=png())
    assert r.status_code == 200
    assert r.json()["filename"] == "proof.png"
    assert r.json()["uploaded_by"] == "[REDACTED_EMAIL_ADDRESS_4]"
    # the bytes went to the table
    assert len(client.table) == 1
    # and the metadata is mirrored onto the finding, which is what the board reads
    mirror = finding(client)["evidence_files"]
    assert len(mirror) == 1
    assert mirror[0]["filename"] == "proof.png"
    assert mirror[0]["id"] == client.table[0]["id"]


def test_upload_joins_the_audit_chain_and_leaves_it_intact(client):
    before = len(client.state["audit"])
    client.post("/flags/f-AI-0042-pol-1/evidence", files=png())
    log = client.state["audit"]
    assert len(log) == before + 1
    assert "evidence:" in log[-1]["step"]
    assert "proof.png" in log[-1]["step"]
    assert "[REDACTED_EMAIL_ADDRESS_4]" in log[-1]["step"]
    assert audit.verify(log) == -1  # the whole chain still hashes


def test_a_second_file_appends_rather_than_replacing(client):
    client.post("/flags/f-AI-0042-pol-1/evidence", files=png("first.png"))
    client.post("/flags/f-AI-0042-pol-1/evidence", files=png("second.png"))
    names = [e["filename"] for e in finding(client)["evidence_files"]]
    assert names == ["first.png", "second.png"]


def test_an_unsupported_type_is_refused(client):
    r = client.post(
        "/flags/f-AI-0042-pol-1/evidence",
        files={"file": ("payload.exe", b"MZ", "application/x-msdownload")},
    )
    assert r.status_code == 400
    assert "unsupported type" in r.json()["detail"]
    assert client.table == []


def test_an_empty_file_is_refused(client):
    r = client.post("/flags/f-AI-0042-pol-1/evidence", files={"file": ("blank.png", b"", "image/png")})
    assert r.status_code == 400
    assert client.table == []


def test_a_file_over_the_ceiling_is_refused(client):
    big = b"x" * (api_mod.MAX_EVIDENCE_BYTES + 1)
    r = client.post("/flags/f-AI-0042-pol-1/evidence", files={"file": ("big.pdf", big, "application/pdf")})
    assert r.status_code == 413
    assert client.table == []


def test_a_dismissed_finding_takes_no_evidence(client):
    finding(client)["status"] = "dismissed"
    r = client.post("/flags/f-AI-0042-pol-1/evidence", files=png())
    assert r.status_code == 409
    assert client.table == []


def test_an_unknown_finding_is_a_404(client):
    r = client.post("/flags/f-AI-0042-pol-9/evidence", files=png())
    assert r.status_code == 404


def test_listing_returns_metadata_without_the_bytes(client):
    client.post("/flags/f-AI-0042-pol-1/evidence", files=png())
    r = client.get("/flags/f-AI-0042-pol-1/evidence")
    assert r.status_code == 200
    row = r.json()[0]
    assert row["filename"] == "proof.png"
    assert row["size"] == len(b"\x89PNG fake bytes")
    assert "data" not in row  # the response model is metadata; bytes need the download route


def test_download_returns_the_bytes_as_an_attachment(client):
    body = b"\x89PNG the real thing"
    client.post("/flags/f-AI-0042-pol-1/evidence", files=png(body=body))
    r = client.get("/evidence/1")
    assert r.status_code == 200
    assert r.content == body
    assert 'filename="proof.png"' in r.headers["content-disposition"]


def test_downloading_something_that_is_not_there_is_a_404(client):
    assert client.get("/evidence/99").status_code == 404

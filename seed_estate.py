"""Load the authored estate (data/estate/assets.json) into Postgres.

Idempotent: wipes ONLY source='seed' rows first, then reloads, so re-running
never duplicates and never touches a real pipeline-assessed asset (D44).
Seeded assets carry an EMPTY audit chain on purpose: no pipeline ran, and a
fabricated chain would contradict the tamper-evident story (the provenance test).

Run:  uv run python seed_estate.py
"""

import json
from datetime import date, timedelta
from pathlib import Path

from app import store
from seed_users import SEEDS  # one source of truth for who the seeded reviewers are

ESTATE = Path(__file__).resolve().parent / "data" / "estate" / "assets.json"

REVIEWERS = [email for email, _pw, role, _su in SEEDS if role == "reviewer"]

# The remediation board would open EMPTY on a fresh machine: authored findings carry
# no owner, no deadline and no state, because in real life a person supplies those.
# This walks the authored findings through a fixed cycle so the board opens alive and
# every filter has something to find, including an overdue item. Index-based rather
# than random, so re-seeding is reproducible.
# NOTE: this adds no audit entries. Seeded assets keep their EMPTY chain (D44),
# because nobody actually did this work; faking a chain would contradict the
# tamper-evident story the product is built on.
SEEDED_FLOW = [
    # (status, due date in days from today or None, give it an owner)
    ("open", None, False),            # unassigned backlog, for the UNASSIGNED filter
    ("in_progress", 5, True),
    ("open", 12, True),
    ("awaiting_evidence", 2, True),
    ("in_progress", -3, True),        # already late, so OVERDUE is never empty
    ("closed", -10, True),
    ("open", None, False),
]


def seed_remediation(assessment: dict, asset_index: int) -> None:
    """Give each authored finding an owner, a deadline and a state, in place."""
    today = date.today()
    for i, f in enumerate(assessment.get("findings") or []):
        if (f.get("status") or "").lower() == "dismissed":
            continue  # a dismissal is a recorded judgement with a reason; never overwrite it
        status, offset, assign = SEEDED_FLOW[(asset_index + i) % len(SEEDED_FLOW)]
        f["status"] = status
        f["due_at"] = (today + timedelta(days=offset)).isoformat() if offset is not None else None
        f["owner"] = REVIEWERS[(asset_index + i) % len(REVIEWERS)] if assign and REVIEWERS else None
        f["evidence_files"] = f.get("evidence_files") or []


def to_state(asset: dict) -> dict:
    assessment = asset.get("assessment") or {}
    return {
        "asset_id": asset["asset_id"],
        "status": "assessed" if assessment else "registered",
        "stage": "done" if assessment else "intake",
        "asset": asset,
        "applicable_inspectors": [],
        "findings_raw": assessment.get("findings", []),
        "inspector_reports": [],
        "risk_tier": assessment.get("risk_tier", ""),
        "risk": assessment.get("risk", {}),
        "decision": assessment.get("decision", ""),
        "audit": [],  # seeds never fake a pipeline chain (D44)
        "error": None,
    }


def main():
    assets = json.loads(ESTATE.read_text())
    store.init_db()
    with store._connect() as conn:
        wiped = conn.execute("DELETE FROM assets WHERE source = 'seed'").rowcount
    for i, a in enumerate(assets):
        seed_remediation(a.get("assessment") or {}, i)
        store.save(to_state(a))
    with store._connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM assets WHERE source = 'seed'").fetchone()[0]
    print(f"wiped {wiped} old seed rows, loaded {n}/{len(assets)}")
    assert n == len(assets), "seed count mismatch"


if __name__ == "__main__":
    main()

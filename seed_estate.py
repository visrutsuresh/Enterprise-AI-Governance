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
    ("dismissed", None, True),        # every board state is represented, including this one
]

# Every desk a flag can sit on, so the TEAM filter has something under each tab.
# None keeps a slice of the backlog unrouted, which is the state a new finding
# starts in and the one the approval agent is woken to change.
SEEDED_ROUTING = ["legal", "risk", "security", "compliance", None, "risk", None]

# A dismissal is only legitimate WITH a written reason, so the seeder never
# produces one without it. Approvals are here too, because "confirmed as raised"
# is a different state from "never looked at" and the board has to show both.
DISMISS_REASON = "Compensating control already signed off by the risk committee; recorded here rather than re-litigated."
APPROVE_REASON = "Confirmed as raised. The remediation work stands."


def seed_remediation(assessment: dict, asset_index: int) -> None:
    """Give each authored finding an owner, a deadline, a desk and a state, in place."""
    today = date.today()
    reviewer = REVIEWERS[asset_index % len(REVIEWERS)] if REVIEWERS else "reviewer@example.com"
    for i, f in enumerate(assessment.get("findings") or []):
        status, offset, assign = SEEDED_FLOW[(asset_index + i) % len(SEEDED_FLOW)]
        f["status"] = status
        f["due_at"] = (today + timedelta(days=offset)).isoformat() if offset is not None else None
        f["owner"] = REVIEWERS[(asset_index + i) % len(REVIEWERS)] if assign and REVIEWERS else None
        f["evidence_files"] = f.get("evidence_files") or []
        f["routed_to"] = SEEDED_ROUTING[(asset_index + i) % len(SEEDED_ROUTING)]

        # a dismissed finding MUST carry the override that dismissed it, or the
        # board would show a judgement nobody made
        if status == "dismissed":
            f["review"] = {"verdict": "overridden", "reason": DISMISS_REASON,
                           "by": reviewer, "at": today.isoformat()}
        elif status == "closed":
            # closed work was confirmed real first, then done, and the proof is attached
            f["review"] = {"verdict": "approved", "reason": APPROVE_REASON,
                           "by": reviewer, "at": today.isoformat()}
            f["evidence_files"] = [{
                "id": 0, "filename": f"{f['finding_id']}-evidence.pdf",
                "size": 18_432, "uploaded_by": f["owner"] or reviewer,
                "at": today.isoformat(), "seeded": True,
            }]


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

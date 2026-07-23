"""Load the authored estate (data/estate/assets.json) into Postgres.

Idempotent: wipes ONLY source='seed' rows first, then reloads, so re-running
never duplicates and never touches a real pipeline-assessed asset (D44).
Seeded assets carry an EMPTY audit chain on purpose: no pipeline ran, and a
fabricated chain would contradict the tamper-evident story (the provenance test).

Run:  uv run python seed_estate.py
"""

import json
from pathlib import Path

from app import store

ESTATE = Path(__file__).resolve().parent / "data" / "estate" / "assets.json"


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
    for a in assets:
        store.save(to_state(a))
    with store._connect() as conn:
        n = conn.execute("SELECT COUNT(*) FROM assets WHERE source = 'seed'").fetchone()[0]
    print(f"wiped {wiped} old seed rows, loaded {n}/{len(assets)}")
    assert n == len(assets), "seed count mismatch"


if __name__ == "__main__":
    main()

import os

import psycopg  # type:ignore
from dotenv import load_dotenv
from fastapi.encoders import jsonable_encoder
from psycopg.rows import dict_row  # type:ignore
from psycopg.types.json import Jsonb  # type:ignore

load_dotenv()
DATABASE_URL = os.environ["DATABASE_URL"]  # points at THIS project's Postgres on port 5435


def _connect():
    return psycopg.connect(DATABASE_URL)


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS assets(
                asset_id TEXT PRIMARY KEY,
                name TEXT,
                type TEXT,
                owner TEXT,
                lifecycle TEXT,
                status TEXT,
                stage TEXT,
                risk_level TEXT,
                risk_tier TEXT,
                source TEXT,
                state JSONB,
                created_at TIMESTAMPTZ
            )
        """)
        # migration seam (the #1 pattern): the CREATE above only fires on a
        # fresh database. When this table needs a new column later, patch
        # existing databases right here with an ALTER TABLE ... IF NOT EXISTS.


def save_pending(asset_id: str, name: str, source: str, created_at) -> None:
    # park the asset as "processing" BEFORE the graph runs, so registration
    # returns instantly and the control tower has a card to show
    minimal = {
        "asset_id": asset_id,
        "status": "processing",
        "stage": "intake",
        "asset": {"asset_id": asset_id, "name": name, "source": source},
    }
    with _connect() as conn:
        conn.execute(
            """INSERT INTO assets (asset_id, name, status, stage, source, state, created_at)
               VALUES (%s, %s, 'processing', 'intake', %s, %s, %s)
               ON CONFLICT (asset_id) DO NOTHING""",
            (asset_id, name, source, Jsonb(minimal), created_at),
        )


def save(state: dict) -> None:
    # upsert the full state blob, and copy the label fields into plain
    # columns so list_all never has to open the blob. source is the D44
    # provenance flag: it is written on every save and shown in the UI.
    asset = state.get("asset") or {}
    risk = (state.get("risk") or {}).get("level")
    tier = (state.get("risk_tier") or "").lower() or None  # the casing trap, handled at the door
    with _connect() as conn:
        conn.execute(
            """INSERT INTO assets (asset_id, name, type, owner, lifecycle, status, stage,
                                   risk_level, risk_tier, source, state, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
               ON CONFLICT (asset_id) DO UPDATE SET
                 name=EXCLUDED.name, type=EXCLUDED.type, owner=EXCLUDED.owner,
                 lifecycle=EXCLUDED.lifecycle, status=EXCLUDED.status, stage=EXCLUDED.stage,
                 risk_level=EXCLUDED.risk_level, risk_tier=EXCLUDED.risk_tier,
                 source=EXCLUDED.source, state=EXCLUDED.state""",
            (
                state["asset_id"],
                asset.get("name"),
                asset.get("type"),
                asset.get("owner"),
                asset.get("lifecycle"),
                state.get("status"),
                state.get("stage"),
                risk,
                tier,
                asset.get("source"),
                Jsonb(jsonable_encoder(state)),
            ),
        )


def get(asset_id: str) -> dict | None:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            "SELECT state, status, stage, created_at FROM assets WHERE asset_id = %s",
            (asset_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        state = row["state"]
        # the columns are fresher than the blob while the graph is running
        # (set_stage and set_status touch only the columns), so stamp the
        # column values back onto the state before handing it out
        state["status"] = row["status"]
        state["stage"] = row["stage"]
        state["created_at"] = row["created_at"]
        return state


def list_all() -> list[dict]:
    # light rows only: the control tower polls this, so it reads the label
    # columns plus an open-findings count, never the whole blob
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("""
            SELECT asset_id, name, type, owner, lifecycle, status, stage,
                   risk_level, risk_tier, source, created_at,
                   (SELECT COUNT(*) FROM jsonb_array_elements(COALESCE(state->'findings_raw', '[]'::jsonb)) AS f
                     WHERE f->>'status' = 'open')::int AS open_findings
            FROM assets ORDER BY created_at DESC
        """)
        return cur.fetchall()


def set_status(asset_id: str, status: str) -> bool:
    with _connect() as conn:
        cur = conn.execute("UPDATE assets SET status = %s WHERE asset_id = %s", (status, asset_id))
        return cur.rowcount > 0


def set_stage(asset_id: str, stage: str) -> bool:
    # graph nodes call this as each stage starts; the control tower polls it live
    with _connect() as conn:
        cur = conn.execute("UPDATE assets SET stage = %s WHERE asset_id = %s", (stage, asset_id))
        return cur.rowcount > 0

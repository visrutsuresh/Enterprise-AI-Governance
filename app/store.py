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

        # tiny key/value table so the active pack survives a restart: a system
        # of record must not silently revert its own rulebook when it reboots
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings(
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

        # Evidence is the ONE part of a finding that is not a fact about the
        # finding: it is a file somebody produced to prove the work was done.
        # It gets a real table rather than a slot in the asset blob, because
        # bytes in JSONB would bloat every read of every asset.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS evidence(
                id SERIAL PRIMARY KEY,
                finding_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                filename TEXT,
                content_type TEXT,
                size INT,
                data BYTEA,
                uploaded_by TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS evidence_finding_idx ON evidence (finding_id)")

        # A measurement is not a fact about the asset, it is a dated snapshot of
        # how the model BEHAVED that month. It gets its own table for the same
        # reason evidence does: history has to be append-only. The raw payload
        # and the derived numbers are both stored, so a figure an auditor saw
        # last quarter is still that figure after the formulas change.
        conn.execute("""
            CREATE TABLE IF NOT EXISTS measurements(
                id SERIAL PRIMARY KEY,
                asset_id TEXT NOT NULL,
                period TEXT NOT NULL,
                payload JSONB,
                computed JSONB,
                uploaded_by TEXT,
                created_at TIMESTAMPTZ DEFAULT now(),
                UNIQUE (asset_id, period)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS measurements_asset_idx ON measurements (asset_id)")


def set_setting(key: str, value: str) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings(key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (key, value),
        )


def all_settings() -> dict:
    with _connect() as conn:
        return dict(conn.execute("SELECT key, value FROM settings").fetchall())


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


def mutate(asset_id: str, change):
    """Read, change, and write back ONE asset inside a single transaction with the
    row locked.

    Why this exists. Every handler used to do get() -> mutate in memory -> save(),
    and save() rewrites the whole JSONB blob. Two reviewers working the same asset
    (one dragging a card, one attaching evidence) both read the same blob, changed
    different parts of it, and both wrote. Last writer won, and the other person's
    change AND their audit-chain entry disappeared. The worst part: verify() still
    reported `intact: true`, because a chain with entries missing from the end is
    internally consistent. A silently-lost audit entry is the one failure this
    product cannot have.

    `change(state)` mutates the state in place and returns whatever the caller
    wants back. If it raises (a 409, a 422), the transaction rolls back and nothing
    is written. Returns None if the asset does not exist.
    """
    with _connect() as conn:  # commits on clean exit, rolls back on exception
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            "SELECT state, status, stage, created_at FROM assets WHERE asset_id = %s FOR UPDATE",
            (asset_id,),
        )
        row = cur.fetchone()
        if row is None:
            return None
        state = row["state"]
        # same column-over-blob stamping get() does: the columns are fresher
        # while the graph is running
        state["status"] = row["status"]
        state["stage"] = row["stage"]
        state["created_at"] = row["created_at"]

        result = change(state)

        asset = state.get("asset") or {}
        cur.execute(
            """UPDATE assets SET name=%s, type=%s, owner=%s, lifecycle=%s, status=%s,
                                 stage=%s, risk_level=%s, risk_tier=%s, source=%s, state=%s
               WHERE asset_id=%s""",
            (
                asset.get("name"),
                asset.get("type"),
                asset.get("owner"),
                asset.get("lifecycle"),
                state.get("status"),
                state.get("stage"),
                (state.get("risk") or {}).get("level"),
                (state.get("risk_tier") or "").lower() or None,
                asset.get("source"),
                Jsonb(jsonable_encoder(state)),
                asset_id,
            ),
        )
        return result


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
                   (SELECT COUNT(*) FROM jsonb_array_elements(
                        COALESCE(state->'asset'->'assessment'->'findings', '[]'::jsonb)) AS f
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


def list_findings() -> list[dict]:
    # every finding in the estate, lifted out of the per-asset JSONB blobs and
    # paired with the asset context the remediation board needs to make sense of
    # it. There is no findings TABLE: findings live inside the asset's assessment,
    # so this flattens with a lateral join the same way list_all counts them.
    # The 4s control-tower poll must keep using list_all; this is heavier.
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("""
            SELECT a.asset_id, a.name AS asset_name, a.risk_tier, a.risk_level,
                   a.owner AS asset_owner, a.created_at, f.value AS finding
            FROM assets a,
                 jsonb_array_elements(
                     COALESCE(a.state->'asset'->'assessment'->'findings', '[]'::jsonb)) AS f
            ORDER BY a.created_at DESC
        """)
        return cur.fetchall()


def add_evidence(
    finding_id: str, asset_id: str, filename: str, content_type: str, data: bytes, uploaded_by: str
) -> dict:
    # returns the metadata row only: the caller never wants the bytes back
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            """INSERT INTO evidence (finding_id, asset_id, filename, content_type, size, data, uploaded_by)
               VALUES (%s, %s, %s, %s, %s, %s, %s)
               RETURNING id, finding_id, asset_id, filename, content_type, size, uploaded_by, created_at""",
            (finding_id, asset_id, filename, content_type, len(data), data, uploaded_by),
        )
        return cur.fetchone()


def list_evidence(finding_id: str) -> list[dict]:
    # metadata only, deliberately: the bytes stay in the table until a download asks
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            """SELECT id, finding_id, asset_id, filename, content_type, size, uploaded_by, created_at
               FROM evidence WHERE finding_id = %s ORDER BY created_at""",
            (finding_id,),
        )
        return cur.fetchall()


def get_evidence(evidence_id: int) -> dict | None:
    # the only read that opens the bytes column
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("SELECT filename, content_type, data FROM evidence WHERE id = %s", (evidence_id,))
        return cur.fetchone()


def save_measurement(asset_id: str, period: str, payload: dict, computed: dict, by: str) -> dict:
    # re-uploading the same period REPLACES it: a corrected snapshot is a fix,
    # not a second truth. The audit chain still records that it happened twice.
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            """INSERT INTO measurements (asset_id, period, payload, computed, uploaded_by)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (asset_id, period) DO UPDATE SET
                 payload=EXCLUDED.payload, computed=EXCLUDED.computed,
                 uploaded_by=EXCLUDED.uploaded_by, created_at=now()
               RETURNING id, asset_id, period, computed, uploaded_by, created_at""",
            (asset_id, period, Jsonb(jsonable_encoder(payload)), Jsonb(jsonable_encoder(computed)), by),
        )
        return cur.fetchone()


def list_measurements(asset_id: str) -> list[dict]:
    # oldest first: the panel draws a trend, and a trend reads left to right
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            """SELECT period, computed, uploaded_by, created_at
               FROM measurements WHERE asset_id = %s ORDER BY period""",
            (asset_id,),
        )
        return cur.fetchall()


def latest_measurement(asset_id: str) -> dict | None:
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute(
            "SELECT period, computed FROM measurements WHERE asset_id = %s ORDER BY period DESC LIMIT 1",
            (asset_id,),
        )
        return cur.fetchone()


def list_metrics_rows() -> list[dict]:
    # richer rows for the executive dashboard: the label columns plus the
    # findings array, decision and human_oversight pulled from the JSONB blob.
    # Heavier than list_all (it opens the assessment), so only the /metrics
    # endpoint calls it, never the 4s control-tower poll.
    with _connect() as conn:
        cur = conn.cursor(row_factory=dict_row)
        cur.execute("""
            SELECT asset_id, lifecycle, status, risk_tier,
                   state->'asset'->'assessment'->>'decision' AS decision,
                   state->'asset'->>'human_oversight' AS human_oversight,
                   COALESCE(state->'asset'->'assessment'->'findings', '[]'::jsonb) AS findings
            FROM assets
        """)
        return cur.fetchall()

"""The canonical asset record (design spec section 2, D32).

One shape for models and agents; `type` tells them apart. Plain dict via
TypedDict so it survives JSON round trips (model output, Postgres JSONB,
the API) untouched.

`source` is the provenance flag (D44): "seed" for authored fixtures,
"pipeline" for real agent output. Shown in the UI, never faked.
"""

import uuid
from typing import TypedDict

from fastapi_users import schemas

ASSET_TYPES = ("model", "agent")
LIFECYCLES = ("proposed", "development", "production", "retired")
SOURCES = ("seed", "pipeline", "manual")  # manual = a human typed the form, no agent involved


class AssetRecord(TypedDict):
    asset_id: str  # "AI-0042"
    type: str  # model | agent
    name: str
    owner: str  # "Priya Raman, Credit Risk"
    purpose: str  # what it does, one plain sentence
    lifecycle: str  # proposed | development | production | retired
    deployment: str  # where it runs, e.g. "AWS eu-west-1, internal API"
    data_touched: list  # e.g. ["customer PII", "credit history"]
    third_party: str | None  # vendor name, or None if in-house
    human_oversight: str  # who checks its output, or "" if nobody
    source: str  # seed | pipeline | manual (D44 provenance flag)
    assessment: dict  # filled by the per-asset graph, empty until assessed
    # --- fields the measurement and scoping work needs ---
    business_unit: str  # whose budget it sits in
    region: str  # where the PEOPLE are, which is what decides the law binding it
    protected_attributes: list  # what fairness is measured across, e.g. ["age_band"]
    last_bias_test_at: str | None  # ISO date, or None if it has never been tested


REQUIRED_ASSET_FIELDS = ("asset_id", "type", "name", "owner", "purpose", "lifecycle", "source")


def valid_asset(a: dict) -> bool:
    return (
        all(a.get(k) for k in REQUIRED_ASSET_FIELDS)
        and a["type"] in ASSET_TYPES
        and a["lifecycle"] in LIFECYCLES
        and a["source"] in SOURCES
    )


# --- what a reviewer may correct, and what counts as a legal value -----------
#
# Every finding in the estate is derived from the asset record. If the inventory
# agent misread the description, the rule never fires, and the hash chain then
# faithfully records a wrong assessment. An uncorrectable record is what turns
# tamper-evidence from an asset into a liability, so this tuple is the whole
# permission model for human edits.

EDITABLE_FIELDS = (
    "name", "type", "owner", "purpose", "lifecycle", "deployment",
    "data_touched", "third_party", "human_oversight",
    "business_unit", "region", "protected_attributes", "last_bias_test_at",
)

LIST_FIELDS = ("data_touched", "protected_attributes")

# the fields packs.fires() matches on. Editing one of these changes which rules
# fire, so the API re-scores immediately rather than leaving a stale verdict.
SCORING_FIELDS = ("type", "lifecycle", "deployment", "data_touched", "third_party", "human_oversight")


def clean_edit(key: str, value) -> tuple[object, str]:
    """(cleaned value, error). An empty error means the value is usable.

    The clerk at the desk: checks the handwriting before it goes in the file.
    A lifecycle of "prod" is handed back; a blank vendor box means in-house,
    which is None, not the empty string.
    """
    if key not in EDITABLE_FIELDS:
        return None, f"{key!r} is not a field a reviewer may change"
    if key in LIST_FIELDS:
        if not isinstance(value, list):
            return None, f"{key} must be a list of short phrases"
        return [str(v).strip() for v in value if str(v).strip()], ""
    if key == "third_party":
        v = str(value).strip() if value is not None else ""
        return (v or None), ""
    v = "" if value is None else str(value).strip()
    if key == "type" and v not in ASSET_TYPES:
        return None, f"type must be one of: {', '.join(ASSET_TYPES)}"
    if key == "lifecycle" and v not in LIFECYCLES:
        return None, f"lifecycle must be one of: {', '.join(LIFECYCLES)}"
    if key in ("name", "owner", "purpose") and not v:
        return None, f"{key} cannot be emptied: it is one of the fields that make a record a record"
    if key == "last_bias_test_at" and v:
        from datetime import date

        try:
            date.fromisoformat(v[:10])
        except ValueError:
            return None, "last_bias_test_at must be a date like 2026-07-31"
    return v, ""


# fastapi-users account shapes, carried from the Papyrus skeleton
class UserRead(schemas.BaseUser[uuid.UUID]):
    role: str


class UserCreate(schemas.BaseUserCreate):
    role: str = "reviewer"


class UserUpdate(schemas.BaseUserUpdate):
    role: str | None = None

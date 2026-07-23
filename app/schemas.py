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
SOURCES = ("seed", "pipeline")


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
    source: str  # seed | pipeline (D44 provenance flag)
    assessment: dict  # filled by the per-asset graph, empty until assessed


REQUIRED_ASSET_FIELDS = ("asset_id", "type", "name", "owner", "purpose", "lifecycle", "source")


def valid_asset(a: dict) -> bool:
    return (
        all(a.get(k) for k in REQUIRED_ASSET_FIELDS)
        and a["type"] in ASSET_TYPES
        and a["lifecycle"] in LIFECYCLES
        and a["source"] in SOURCES
    )


# fastapi-users account shapes, carried from the Papyrus skeleton
class UserRead(schemas.BaseUser[uuid.UUID]):
    role: str


class UserCreate(schemas.BaseUserCreate):
    role: str = "reviewer"


class UserUpdate(schemas.BaseUserUpdate):
    role: str | None = None

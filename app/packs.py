"""Pack loader: the NFR-1 swap point.

Which company policy and which regulation the app enforces is decided by
two env vars (POLICY_PACK, FRAMEWORK_PACK), read at CALL time so a swap
needs no restart of anything but the request. Paths are anchored to this
file (the Papyrus 33a fix): starting the server from the wrong directory
can never silently blank the packs.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _load(kind: str, env_var: str, name: str | None = None) -> dict:
    # an explicit name wins; the env var is the estate-wide DEFAULT, not the law
    name = (name or os.getenv(env_var, "")).strip()
    if not name:
        raise RuntimeError(f"{env_var} missing from the environment; the app cannot assess without a pack")
    path = DATA_DIR / kind / f"{name}.json"
    if not path.exists():
        raise RuntimeError(f"pack '{name}' not found at {path}")
    return json.loads(path.read_text())


def load_policy_pack(name: str | None = None) -> dict:
    return _load("policy_packs", "POLICY_PACK", name)


def load_framework_pack(name: str | None = None) -> dict:
    return _load("framework_packs", "FRAMEWORK_PACK", name)


def available() -> dict:
    """Every pack file on disk, so the UI offers a real choice instead of a
    hard-coded pair of names."""

    def names(kind: str) -> list:
        d = DATA_DIR / kind
        return sorted(p.stem for p in d.glob("*.json")) if d.exists() else []

    return {"policy_packs": names("policy_packs"), "framework_packs": names("framework_packs")}


def chosen(state: dict) -> dict:
    """Which rulebooks bind THIS asset. One estate, many rulebooks: a credit
    model serving EU customers and an internal document sorter are not under the
    same law, so the choice belongs on the asset. An asset that never chose
    falls through to the env vars, which is why the global swap demo still works.
    """
    picked = state.get("packs") or {}
    return {
        "policy": picked.get("policy") or os.getenv("POLICY_PACK", ""),
        "framework": picked.get("framework") or os.getenv("FRAMEWORK_PACK", ""),
        "extra_frameworks": picked.get("extra_frameworks") or [],
    }


def fires(rule: dict, asset: dict) -> bool:
    """Does this policy rule's applies_to match this asset? Deterministic, the
    match spec documented in data/framework_packs/README.md. Used by the bulk
    pack-swap re-score; the live inspectors make the same call with judgement."""
    for field, want in rule.get("applies_to", {}).items():
        have = asset.get(field)
        if want is True:
            ok = bool(have)
        elif want is None:
            ok = not have
        elif isinstance(want, list):
            if isinstance(have, list):
                ok = bool({str(w).lower() for w in want} & {str(h).lower() for h in have})
            else:
                ok = any(str(w).lower() in str(have or "").lower() for w in want)
        else:
            ok = have == want
        if not ok:
            return False
    return True

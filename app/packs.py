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


def _load(kind: str, env_var: str) -> dict:
    name = os.getenv(env_var, "")
    if not name:
        raise RuntimeError(f"{env_var} missing from the environment; the app cannot assess without a pack")
    path = DATA_DIR / kind / f"{name}.json"
    if not path.exists():
        raise RuntimeError(f"pack '{name}' not found at {path}")
    return json.loads(path.read_text())


def load_policy_pack() -> dict:
    return _load("policy_packs", "POLICY_PACK")


def load_framework_pack() -> dict:
    return _load("framework_packs", "FRAMEWORK_PACK")


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

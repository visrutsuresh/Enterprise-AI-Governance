import hashlib
from datetime import datetime, timezone

GENESIS = "0" * 64  # "block 0" fingerprint the first real entry links back to


def _hash(prev: str, material: str) -> str:
    return hashlib.sha256(f"{prev}|{material}".encode()).hexdigest()


def _material(entry: dict) -> str:
    # entries written since ts/by landed hash all three fields, so a forged
    # timestamp or actor breaks the chain exactly like a forged step does.
    # older entries hashed the step alone; verify must keep accepting them.
    if "ts" in entry:
        return f"{entry['step']}|{entry['ts']}|{entry.get('by') or ''}"
    return str(entry["step"])


def _append(existing: list, new: list, by: str | None) -> list:
    log = list(existing) if existing else []
    prev = log[-1]["hash"] if log else GENESIS
    for step in new:
        entry = {"step": step, "ts": datetime.now(timezone.utc).isoformat(), "by": by, "prev": prev}
        entry["hash"] = _hash(prev, _material(entry))
        log.append(entry)
        prev = entry["hash"]
    return log


def chain(existing: list, new: list) -> list:  # LangGraph reducer, replaces operator.add; MUST stay (a, b) -> c
    return _append(existing, new, None)


def chain_as(existing: list, new: list, by: str) -> list:
    # API call sites use this so the acting human is a hashed field, not prose
    return _append(existing, new, by)


def verify(log: list) -> int:  # -1 if intact, else index of first broken entry
    prev = GENESIS
    for i, entry in enumerate(log):
        if entry["prev"] != prev or entry["hash"] != _hash(prev, _material(entry)):
            return i
        prev = entry["hash"]
    return -1

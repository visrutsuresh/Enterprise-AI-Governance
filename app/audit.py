import hashlib

GENESIS = "0" * 64  # "block 0" fingerprint the first real entry links back to


def _hash(prev: str, step: str) -> str:
    return hashlib.sha256(f"{prev}|{step}".encode()).hexdigest()


def chain(existing: list, new: list) -> list:  # LangGraph reducer, replaces operator.add
    log = list(existing) if existing else []
    prev = log[-1]["hash"] if log else GENESIS
    for step in new:
        h = _hash(prev, str(step))
        log.append({"step": step, "prev": prev, "hash": h})
        prev = h
    return log


def verify(log: list) -> int:  # -1 if intact, else index of first broken entry
    prev = GENESIS
    for i, entry in enumerate(log):
        if entry["prev"] != prev or entry["hash"] != _hash(prev, str(entry["step"])):
            return i
        prev = entry["hash"]
    return -1

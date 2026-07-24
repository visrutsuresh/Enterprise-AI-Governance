"""The headline test for an audit product: a forged entry is detected."""

from app.audit import chain, verify


def test_chain_intact():
    log = chain([], ["step one", "step two"])
    log = chain(log, ["step three"])
    assert len(log) == 3
    assert verify(log) == -1


def test_forged_entry_detected():
    log = chain([], ["inventory done", "policy_compliance done", "decision: flagged (2 findings)"])
    log[1]["step"] = "policy_compliance done: all clear"  # the cover-up
    assert verify(log) == 1


def test_forged_hash_detected():
    log = chain([], ["a", "b"])
    log[1]["hash"] = "0" * 64  # recomputing the hash does not help the attacker
    assert verify(log) == 1


def test_deleted_entry_detected():
    log = chain([], ["a", "b", "c"])
    del log[1]  # removing a step breaks the link to the next one
    assert verify(log) == 1


def test_empty_log_is_intact():
    assert verify([]) == -1

"""D44 guarded: seeded fixtures never masquerade as pipeline output.

The product's headline is a tamper-evident audit trail; a fabricated chain
on an authored fixture would contradict the product.
"""

import json
from pathlib import Path

from seed_estate import to_state

ESTATE = Path(__file__).resolve().parent.parent / "data" / "estate"


def _assets():
    return json.loads((ESTATE / "assets.json").read_text())


def test_no_estate_asset_claims_a_pipeline_ever_ran_on_it():
    """The invariant the provenance flag exists for. 'seed' is an authored fixture
    and 'manual' is a record a human typed with no agent involved: both are true of
    data in this file. 'pipeline' would claim an agent assessed it, and no agent has
    ever seen these. Faking that one value would undermine the audit trail's whole
    story, so it is the one this test forbids outright."""
    assets = _assets()
    assert len(assets) >= 180
    assert all(a["source"] in ("seed", "manual") for a in assets)
    assert not any(a["source"] == "pipeline" for a in assets)


def test_both_authored_provenance_values_are_actually_present():
    """A value that appears in no row is a branch the UI badge never renders."""
    sources = {a["source"] for a in _assets()}
    assert sources == {"seed", "manual"}


def test_a_manually_entered_asset_carries_no_assessment():
    """Nobody assessed these, so nothing may claim they were: empty findings, no tier."""
    for a in _assets():
        if a["source"] == "manual":
            assert not (a.get("assessment") or {}).get("findings")
            assert not (a.get("assessment") or {}).get("risk_tier")


def test_seeds_enter_the_store_with_an_empty_chain():
    for a in _assets():
        state = to_state(a)
        assert state["audit"] == [], f"{a['asset_id']} would get a fabricated chain"


def test_labeled_set_never_overlaps_the_estate():
    # if an inspector could retrieve a planted answer as precedent, the
    # bench's recall would measure nothing
    estate_ids = {a["asset_id"] for a in _assets()}
    labeled_ids = {e["asset"]["asset_id"] for e in json.loads((ESTATE / "labeled.json").read_text())}
    assert len(labeled_ids) == 15
    assert not (estate_ids & labeled_ids)

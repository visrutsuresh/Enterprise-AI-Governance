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


def test_every_estate_asset_is_marked_seed():
    assets = _assets()
    assert len(assets) >= 180
    assert all(a["source"] == "seed" for a in assets)


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

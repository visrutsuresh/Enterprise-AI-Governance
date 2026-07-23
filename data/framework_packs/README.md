# Pack shapes

The app never hardcodes a law or a company policy. Both live here as JSON,
selected by env var (`FRAMEWORK_PACK`, `POLICY_PACK`), loaded by `app/packs.py`.
Swapping regulation = dropping in a new JSON file + changing one env var.
No code change (NFR-1).

## Framework pack (`framework_packs/<name>.json`)

The regulation as data. Shape:

```json
{
  "pack_id": "eu_ai_act-v1",
  "name": "human-readable name",
  "tiers": [
    {
      "tier": "high",
      "rank": 1,
      "description": "what this tier means",
      "criteria": ["plain-text indicators the risk inspector matches an asset against"],
      "controls": [
        { "id": "EU-H-02", "title": "short name", "requirement": "what the asset must have" }
      ]
    }
  ]
}
```

- `rank` orders tiers worst-first (0 = worst). Tier names are pack-specific:
  the EU AI Act has unacceptable/high/limited/minimal; a NIST or ISO pack can
  use its own vocabulary. Code must key off `rank`, never a hardcoded tier name.
- `criteria` are read by the risk_assessment inspector to pick the tier.
- `controls` are what findings pin to (`control_id`).

To add NIST AI RMF or ISO 42001: write a new file in this shape, set
`FRAMEWORK_PACK=<filename without .json>`. That is the whole plug-in point.

## Policy pack (`policy_packs/<name>.json`)

Company rules as data. Shape:

```json
{
  "pack_id": "acme-v1",
  "name": "human-readable name",
  "rules": [
    {
      "id": "POL-01",
      "title": "the rule, stated as its violation",
      "applies_to": { "data_touched": ["customer PII"], "third_party": true },
      "severity": "high"
    }
  ]
}
```

`applies_to` is a match spec over asset-record fields (see `app/schemas.py`).
A rule FIRES when every entry matches, i.e. it describes the violating asset:

- list value on a list field (`data_touched`): fires if any listed value is present
- list value on a string field (`lifecycle`, `type`, `deployment`): fires if the
  field equals or contains any listed value
- `true`: fires if the field is non-empty / non-null
- `null`: fires if the field is empty or missing

`severity` is always lowercase high | medium | low (the casing trap).

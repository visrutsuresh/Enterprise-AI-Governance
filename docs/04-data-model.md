# 04. Data Model

**Version 1, 2026-07-28.** Three kinds of storage: Postgres for the estate, Weaviate for precedent, and plain files for the rulebooks.

## 1. Postgres, database `governance`

### `assets`

| Column | Type | Meaning |
|---|---|---|
| `asset_id` | TEXT, primary key | Identity, for example `AI-0042` |
| `name`, `type`, `owner`, `lifecycle` | TEXT | Denormalised from the canonical record, for estate filtering |
| `status` | TEXT | `processing`, `assessed`, `flagged`, `error` |
| `stage` | TEXT | Narration while an assessment runs |
| `risk_level` | TEXT | `high`, `medium`, `low`, rolled up deterministically |
| `risk_tier` | TEXT | The regulatory tier, lower-cased at fan-in |
| `source` | TEXT | `seed` for the synthetic estate, `live` for one registered through the tower |
| `state` | JSONB | The whole assessment: record, findings, reports, risk, decision, audit chain |
| `created_at` | TIMESTAMPTZ | Registration time |

The `source` column matters more than it looks: it is how a genuinely live registration is told apart from the seeded estate during a demonstration.

### Accounts

Roles are `reviewer` and `admin`. **No open signup**; an administrator creates every account.

## 2. The canonical asset record

Produced by the inventory agent from a paragraph of prose: name, type, owner, lifecycle stage, purpose, the data it touches, who it affects, whether a human reviews its output, and the like. This canonicalisation is the whole reason a registration can be a paragraph rather than a form.

## 3. The finding shape

| Field | Meaning |
|---|---|
| `finding_id` | Stable id, carrying the asset and the inspector |
| `inspector` | Which of the five raised it |
| `control_id` | The policy rule or framework control it pins to |
| `severity` | high, medium or low |
| `plain` | What it means in everyday words |
| `evidence` | The fact in the record that triggered it |
| `remediation` | What to do about it |
| `status` | Open, or routed to a reviewer |

A finding missing any required field is discarded before it reaches a reviewer, and the drop is counted.

## 4. Packs, as data

| Kind | Location | Contents |
|---|---|---|
| Policy packs | `data/policy_packs` | A company's own rules, each with a machine-readable applicability spec |
| Framework packs | `data/framework_packs` | A regulatory framework's controls |
| Estate | `data/estate` | The synthetic asset corpus |

Two policy packs and one framework pack ship with the system, which is what makes the swap demonstrable: activating the other pack re-scores the estate deterministically.

## 5. The seeded estate

185 synthetic assets, plus a 15-asset labelled answer key with **zero overlap** with the rest, used for the benchmark. Seeded assets carry deliberately **empty audit chains**, so that any chain you see was produced by a real run rather than by the seeder.

## 6. Weaviate, collection for precedent

Prior assessments, retrievable by similarity so a later asset can cite an earlier ruling. Embeddings are computed locally, with the cache pinned inside the repository after a temporary-directory cache corrupted itself.

## 7. Audit chain

Per asset, one entry per pipeline step, each sealed against the previous. Read through the audit endpoint, which verifies on read and reports the first broken index. Tested by forging an entry directly in Postgres: the break was reported at the exact index.

## 8. Retention

Nothing is deleted. Assets, assessments, findings and audit chains are kept indefinitely, which suits a governance record. There is no purge and no deletion endpoint. The whole estate is synthetic.

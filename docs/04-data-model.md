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

### `evidence`

| Column | Type | Meaning |
|---|---|---|
| `id` | SERIAL, primary key | Download handle |
| `finding_id` | TEXT, indexed | The finding this proves work on |
| `asset_id` | TEXT | Denormalised so evidence can be swept per asset without opening any blob |
| `filename`, `content_type` | TEXT | As uploaded |
| `size` | INT | Bytes, computed server-side rather than trusted from the client |
| `data` | BYTEA | The file itself |
| `uploaded_by` | TEXT | The account's email |
| `created_at` | TIMESTAMPTZ | Upload time |

**Why this is a table when the four remediation fields were not.** Those were small scalars, so putting them in the existing JSONB avoided a migration and cost nothing. Bytes are different: the asset blob is read in full on every estate view, and a few screenshots inside it would slow down every one of those reads for the sake of a column almost nobody opens. So the bytes get a table, and only the file's *metadata* is mirrored onto the finding, which lets the board show a count per card without a second query. **The table is the source of truth for content; the mirror is a display convenience.**

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
| `status` | One of `open`, `in_progress`, `awaiting_evidence`, `closed`, `dismissed`. Only an override can set `dismissed`, and a dismissed finding cannot be moved again |
| `owner` | Email of the person remediating it, or null for unassigned |
| `due_at` | ISO date the remediation is due, or null |
| `evidence_files` | List of attached proof references, empty until evidence upload ships |
| `routed_to` | The team it was routed to, if it has been |
| `review` | The reviewer's verdict, once given: verdict, reason, who, and when |

The four remediation fields (`status` beyond its original two words, `owner`, `due_at`, `evidence_files`) were added inside the existing JSONB shape on 2026-07-28, so **no migration ran**: a finding written before then simply reads as unassigned and `open`, which is exactly what it means. One consequence is accepted and documented rather than solved: a finding update is a read-modify-write of one asset's JSON document, so two people editing findings on the same asset at the same moment can clobber each other. Acceptable for two reviewers on a demo estate; row locking would cost more than it buys this week.

A finding missing any required field is discarded before it reaches a reviewer, and the drop is counted.

**Why an approval leaves the status alone.** Approving a finding confirms it is real, so the remediation work still exists and it must keep counting as open. Only an override closes it. That keeps the estate's open-finding counts meaning "work outstanding" rather than "not yet looked at".

## 4. Packs, as data

| Kind | Location | Contents |
|---|---|---|
| Policy packs | `data/policy_packs` | A company's own rules, each with a machine-readable applicability spec |
| Framework packs | `data/framework_packs` | A regulatory framework's controls |
| Estate | `data/estate` | The synthetic asset corpus |

Two policy packs and one framework pack ship with the system, which is what makes the swap demonstrable: activating the other pack re-scores the estate deterministically.

## 5. The seeded estate

185 synthetic assets, plus a 15-asset labelled answer key with **zero overlap** with the rest, used for the benchmark. Seeded assets carry deliberately **empty audit chains**, so that any chain you see was produced by a real run rather than by the seeder.

Since 2026-07-28 the seeder also walks findings through a fixed index-based cycle of owners, due dates and statuses, so the remediation board opens populated rather than empty (at full scale roughly: 120 open, 79 in progress, 39 awaiting evidence, 39 closed, 79 unassigned, 39 overdue). The cycle is deterministic, so re-seeding is reproducible; it adds no audit entries, so the empty-chain rule above still holds; and it never overwrites a dismissed finding.

## 6. Weaviate, collection for precedent

Prior assessments, retrievable by similarity so a later asset can cite an earlier ruling. Embeddings are computed locally, with the cache pinned inside the repository after a temporary-directory cache corrupted itself.

## 7. Audit chain

Per asset, one entry per pipeline step, each sealed against the previous. Read through the audit endpoint, which verifies on read and reports the first broken index. Tested by forging an entry directly in Postgres: the break was reported at the exact index.

## 8. Retention

Nothing is deleted. Assets, assessments, findings and audit chains are kept indefinitely, which suits a governance record. There is no purge and no deletion endpoint. The whole estate is synthetic.

# 03. Low-Level Design

**Version 1, 2026-07-28.**

## 1. The state object

| Key | Written by | Holds |
|---|---|---|
| `asset_id` | caller | Identity |
| `status` | several | `processing`, `assessed`, `flagged`, `error` |
| `stage` | every node | Narration: intake, orchestrating, inspecting, rolling up, done |
| `description` | caller | The messy registration text |
| `asset` | inventory | The canonical record |
| `applicable_inspectors` | orchestrate | Which inspectors apply, defaulting to all five |
| `findings_raw` | five inspectors, append-only | Findings before validation |
| `inspector_reports` | five inspectors, append-only | Per inspector: ok or failed, plus a note |
| `risk_tier` | risk assessment, lower-cased at fan-in | The regulatory tier |
| `risk` | fan-in | Level, score, why |
| `decision` | decide | `compliant` or `flagged` |
| `audit` | every node | The hash chain, append-only |

**The casing trap:** the tier comes back written the way the model wrote it, capitalised or not. It is lower-cased once, at fan-in, and every reader downstream relies on that. Any new reader must not assume the raw value.

## 2. The finding shape

A finding carries a finding id, the inspector, the **control id** it pins to (a rule from the policy pack or a control from the framework pack), a severity, a plain-English line, the evidence that triggered it, a remediation, and a status. Anything missing a required field is discarded before display and counted.

Since 2026-07-28 a finding also carries its remediation state: an `owner`, a `due_at` date, an `evidence_files` list, and a five-word `status` vocabulary (`open`, `in_progress`, `awaiting_evidence`, `closed`, `dismissed`). These live inside the same JSONB shape, so no migration ran and findings written earlier read as unassigned and open. `store.list_findings()` flattens findings across the estate the same way the open-finding counter always has, and `PATCH /flags/{finding_id}` does the read-modify-write; both follow the existing single-table pattern rather than normalising into a findings table (a five-hour job instead of twelve, at the accepted cost of last-write-wins on concurrent edits to one asset).

Pinning every finding to a control id is what makes the audit trail defensible: a reviewer can ask which rule this came from and get an answer.

## 3. Packs as data

Two kinds of pack live as files rather than code: policy packs (a company's own rules) and framework packs (a regulatory framework's controls).

- Packs are **loaded at call time**, anchored to the code rather than the working directory, so changing the active pack needs no restart and no redeployment.
- Each policy rule carries a machine-readable applicability spec. Plain code decides whether a rule fires for an asset by matching that spec against the asset's fields.
- Because matching is deterministic, **swapping the active pack re-scores the whole estate without a single model call.** Measured: one pack produced 194 findings across 111 assets, the other 147 across 114, with 86 assets re-scored, and every audit chain left intact.

The honest limit, stated on the demonstration path: regulatory **tiers** do not move in a re-score, because assigning a tier needs the model.

## 4. Agents

| Agent | Role |
|---|---|
| `inventory` | Plain-language description to a canonical record |
| `orchestrate` | Which inspectors apply to this asset |
| `policy_compliance` | Breaches of the active policy pack |
| `risk_assessment` | The regulatory risk tier and risk findings |
| `data_governance` | What data is touched, on what basis, with what retention |
| `responsible_ai` | Fairness, bias testing, transparency, human oversight |
| `security_third_party` | Model supply chain, third-party services, access |
| `model_monitoring` | Sweep only: drift and performance signals |
| `regulatory_intel` | Sweep only: what changed in the rules |
| `audit_reporting` | Sweep only: reporting over the estate |

Each inspector is a reasoning loop with a step ceiling and seven read-only tools: read the registry, read the policy pack, read the framework pack, search precedent, read an asset's history, read its audit trail, and read the active pack. All are read-only by design: a governance system that could change what it governs would not be a governance system.

## 5. Guards and failure handling

Every node is wrapped with a bounded wall-clock and one retry, recording failure into the state rather than raising.

| Failure | Behaviour |
|---|---|
| One inspector fails both attempts | Marked failed with a note; the others still produce findings |
| The orchestrator finds nothing applicable | The graph ends cleanly rather than running five inspectors for nothing |
| Model output carries a second JSON object | The parser takes the first complete object |
| Parallel inspectors arrive together | The lane batches up to 8 requests inside its single GPU container (vLLM, since 2026-07-28); the platform-side single-container cap still prevents a second billed GPU. The old client-side lock is gone |
| A stray server error from the lane | One retry, because a container swap surfaces exactly this way |

## 6. Deterministic by choice

Three things are plain code and must stay that way, because they are what makes the benchmark meaningful:

1. **The risk roll-up.** Agents never write it.
2. **Pack applicability matching.** A rule fires or it does not.
3. **The decision.** Compliant or flagged, from the findings, never a model's opinion, and never an automatic block.

## 7. Module map

| Module | Responsibility |
|---|---|
| `api.py` | Endpoints, authentication, background processing |
| `app/graph.py` | Nine nodes, guards, the conditional fan-out |
| `app/agents.py` | Ten agent prompts and the inspector runner |
| `app/agents_base.py` | The reasoning loop and the JSON parser |
| `app/packs.py` | Pack loading and applicability matching |
| `app/sweep.py` | Estate sweep, deterministic re-scoring, estate metrics |
| `app/tools.py` | The seven read-only tools |
| `app/router.py` | The single model lane |
| `app/store.py` | Postgres access |
| `app/precedent.py` | Weaviate collection |
| `app/state.py` | Shapes, validation, risk roll-up |
| `app/audit.py` | Hash chain |
| `app/users.py` | Accounts, roles, sessions |

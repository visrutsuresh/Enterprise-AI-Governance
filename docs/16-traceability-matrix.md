# 16. Traceability Matrix

**Version 1, 2026-07-28.** Each requirement from [01-requirements.md](01-requirements.md), the code that satisfies it, and the test or measurement that proves it.

## Functional

| Req | Verdict | Code | Proof |
|---|---|---|---|
| FR-1 register from a plain-language description | MET | `POST /assets`, `inventory_agent` in `app/agents.py` | Live registration, 2026-07-27 |
| FR-2 central inventory | MET | `app/store.py`, `GET /assets`, the estate seed | 185 seeded assets |
| FR-3 policy and framework packs as data | MET | `app/packs.py`, `data/policy_packs`, `data/framework_packs` | `test_config_swap.py` |
| FR-4 five inspection dimensions | MET | Five inspector agents, parallel step in `app/graph.py` | Benchmark: violation recall 74.3% |
| FR-5 choose applicable inspectors | MET | `orchestrate_agent`, conditional fan-out in `app/graph.py` | Recorded in the state per asset |
| FR-6 regulatory risk tier | MET | `risk_assessment_agent`, lower-cased at fan-in | Benchmark: tier accuracy 73.3%; `test_fanin.py` covers the casing |
| FR-7 deterministic risk roll-up | MET | `risk_rollup()` in `app/state.py` | `test_state.py`, `test_fanin.py` |
| FR-8 findings complete and control-referenced | MET | `valid_finding()`, `_stamp` in `app/agents.py` | `test_fanin.py`, `test_state.py` |
| FR-9 route a flag, never auto-block | MET | `POST /flags/{id}/route`; no blocking endpoint exists | Proved by absence: there is no such code path |
| FR-9a record the reviewer's verdict, with a reason for any dismissal | MET | `POST /flags/{id}/decision` in `api.py`; the verdict joins the asset's hash chain | `test_flag_decision.py` (8 tests) plus a live probe against the real database |
| FR-9b remediation as tracked work: owner, due date, status, board | MET | `GET /remediation` and `PATCH /flags/{id}` in `api.py`, `store.list_findings()`, the `/remediation` board with dnd-kit | `test_remediation.py` (19 tests): vocabulary enforced, filters exact, every change audit-chained, dismissed findings immovable, approved findings still open |
| FR-10 swap the rulebook and re-score | MET | `POST /packs/activate`, `rescore_policy()` in `app/sweep.py` | `test_config_swap.py`; measured 194 findings across 111 assets to 147 across 114, 86 re-scored, chains intact |
| FR-11 estate sweep | MET | `run_sweep()` in `app/sweep.py`, three sweep agents | Exercised live |
| FR-12 executive brief | MET | `GET /brief` | Exercised live |
| FR-13 tamper-evident audit per asset | MET | `app/audit.py`, `GET /assets/{id}/audit` | `test_audit.py` (5 tests); verified live against a forged database row; benchmark audit completeness 1.0 |
| FR-14 administrator-created accounts | MET | `app/users.py`, the users endpoints | Role gates in the API |

## Non-functional

| Req | Verdict | Evidence |
|---|---|---|
| NFR-1 rules as data, swappable without a restart | MET | Call-time pack loading anchored to the code; `test_config_swap.py` |
| NFR-2 no third-party model | MET | One lane in `app/router.py`; no cloud client exists. **Not covered by a test** |
| NFR-3 unattended assessment in minutes | MET | About 220 seconds live; 15 of 15 completed in the benchmark |
| NFR-4 a stuck agent cannot hang an assessment | MET | `guarded()` in `app/graph.py` |
| NFR-5 tampering detectable | MET | `test_audit.py` plus the live forged-row check |
| NFR-6 deterministic parts stay deterministic | MET | Roll-up, matching and decision are plain code; `test_fanin.py`, `test_config_swap.py` |
| NFR-7 synthetic estate, secrets outside the repository | MET | 185 synthetic assets; ignored environment file |
| NFR-8 reuse of the skeleton | MET | Forked from the contract-review system; duplication measured in the planning repository |

## Coverage summary

53 automated tests, no model calls, covering the audit chain, the fan-in reducer including the tier casing fix, validation, the reasoning loop, provenance (seeded against live), the pack swap, the benchmark's own scoring, the flag-decision endpoint, and the remediation queue and board endpoints.

The gaps, stated plainly: endpoint coverage is still **partial**, since only the flag-decision and remediation endpoints are exercised by tests (registration, packs, sweep and the brief are verified by hand and by live probes), and there is **no test asserting that asset descriptions can never reach a third party**, which currently rests on the absence of any cloud client in the codebase.

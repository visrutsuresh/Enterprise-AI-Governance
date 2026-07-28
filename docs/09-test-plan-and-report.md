# 09. Test Plan and Report

**Version 1, 2026-07-28.**

## 1. Strategy

| Layer | Cost | What it proves |
|---|---|---|
| Automated tests (`tests/`) | free, zero model calls | The deterministic seams: validation, fan-in, the audit chain, pack swapping, provenance, the reasoning loop, benchmark scoring |
| Live probes | free or cheap | That a registration really flows through the pipeline and leaves an intact chain |
| Benchmark (`bench.py`) | GPU money | Tier accuracy, violation recall, flag precision and audit completeness against a labelled answer key. See [10-benchmark-report.md](10-benchmark-report.md) |

## 2. Running them

```bash
uv run python -m pytest tests/ -q
```

Use `python -m pytest`, not `pytest` alone, or collection cannot find the application package.

## 3. Coverage

**53 tests, green in about a second, no model calls.**

| File | Tests | Covers |
|---|---|---|
| `test_remediation.py` | 19 | The remediation queue and board, driven through the real endpoints with the database swapped for a dict: the status vocabulary is enforced (a word outside the four board columns is refused with 422, and the error points at the override path), an unknown finding 404s, each filter (`mine`, `unassigned`, `overdue`, `team`, `status`) returns only matching findings, owner and due date set and clear correctly, a malformed date is refused, every change grows that asset's hash chain by exactly one and leaves the verifier intact, a dismissed finding refuses to be moved with 409, and an approved finding is still `open` and therefore still on the board |
| `test_flag_decision.py` | 8 | The reviewer's verdict on a flag, driven through the real endpoint with the database swapped for a dict: approve confirms and leaves the work open, override dismisses and keeps the reason, an override with no reason is refused, an unknown verdict is refused, a flag cannot be decided twice, unknown finding and unknown asset both 404, the verdict joins the hash chain and the chain still verifies, and the decision is actually persisted |
| `test_audit.py` | 5 | The hash chain and its verifier |
| `test_bench_scoring.py` | 5 | The benchmark's own scoring, so the numbers it reports are trustworthy |
| `test_fanin.py` | 5 | Finding validation, the casing fix on the tier, and the deterministic roll-up |
| `test_state.py` | 4 | Shapes and the risk roll-up |
| `test_provenance.py` | 3 | That seeded assets and live registrations stay distinguishable |
| `test_react.py` | 3 | The reasoning loop |
| `test_config_swap.py` | 1 | That activating a different pack re-scores deterministically |

Testing the benchmark's scoring is worth calling out: a measurement harness nobody checks is a good way to publish a wrong number confidently.

## 4. What testing and live probing have caught

- **Open-finding counts were computed from raw inspector output rather than the canonical assessment**, so estate counts would have silently frozen after any sweep or re-score. Found by testing, fixed the same session.
- **The reasoning loop's JSON parser broke deterministically** when the model emitted a second object; one inspector failed twice at the identical character. Fixed here and in the sibling system.
- **This repository was running an older model router** than its sibling, missing the single-lane lock and the retry. Ported across.
- **The tamper-evidence claim was verified end to end** by forging an entry directly in Postgres and confirming the endpoint reported the break at the exact index.

## 5. Live verification of the flag decision, 2026-07-28

Run against the real API and the real estate database, no model calls: signed in as an administrator, took an undecided open finding from a seeded asset, confirmed that an override with an empty reason is refused with 422, recorded an override with a reason, confirmed a second decision on the same flag returns 409, and read the audit endpoint back. The chain grew by one entry naming the finding, the verdict, the reviewer and the reason, and still verified as intact. The estate row's open-finding count dropped by one. The probe's write was then reverted, so the seeded estate is untouched.

## 6. Live registration verification

One asset was registered through the tower on a warm lane and assessed end to end: the correct regulatory tier for an employment-screening system, five findings across four inspectors covering a missing bias test, no named human reviewer and no kill switch, an intact eight-entry audit chain, in about 220 seconds. It is retained in the estate marked as a live registration, which is how it stays distinguishable from the seeded 185.

## 7. Known gaps

| Gap | Why it matters |
|---|---|
| Thin endpoint-level coverage | The flag-decision and remediation endpoints are covered by tests. Registration, packs, sweep and the brief are still verified by hand and by live probes. **This became possible on 2026-07-28**: the module used to create its database tables at import, so it could not be imported without Postgres, which is why no endpoint tests existed. Table creation moved into the startup hook |
| No frontend test of the drag interaction | The board's drag and drop is verified by hand; both the board and the ALL rows view read the same endpoint, so a card can always be moved without dragging if it fails live |
| No test asserting asset text never leaves for a third party | The claim rests on the absence of a cloud client |
| No frontend tests | The tower is verified by hand |
| Tier accuracy is only measurable through the paid benchmark | There is no free proxy for it |

## 8. Test data

A 185-asset synthetic estate, and a **15-asset labelled answer key with zero overlap** with it, so the benchmark measures judgement rather than retrieval. Seeded assets carry empty audit chains, so any chain in the system was produced by a real run.

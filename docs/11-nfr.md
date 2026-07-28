# 11. Non-Functional Requirements

**Version 1, 2026-07-28.**

## 1. Performance

| Property | Target | Measured |
|---|---|---|
| One asset assessed | minutes, unattended | about 220 seconds on a warm lane, live |
| First call after the lane idles | under two minutes | roughly 60 to 90 seconds |
| Per-node ceiling | bounded, with one retry | 1200 seconds |
| Registration response | immediate | The asset is parked as processing before any model runs |
| Estate re-score after a pack swap | instant, and free | Deterministic matching, no model calls |
| Full labelled benchmark | one warm window | 15 assets, zero retries |

The re-score deserves emphasis: changing the rulebook for 185 assets costs nothing and finishes immediately, because applicability is plain code.

## 2. Scale

Single concurrent user, an estate of 185 synthetic assets, one assessment at a time. The estate views, the sweep and the brief operate over the whole estate; only the per-asset pipeline is expensive.

## 3. Availability

No availability target, no failover. The guarantee that is met: **a failure is recorded rather than hidden.** A failing inspector is marked failed with a note and the assessment continues; a failing node records into the state instead of raising; an asset that cannot be assessed ends in an explicit error status rather than staying at processing.

## 4. Privacy

| Requirement | Status |
|---|---|
| Asset descriptions never reach a third-party model | Met: one lane, no cloud client in the codebase |
| Embeddings computed locally | Met, with the cache pinned inside the repository |
| No open signup | Met |

An inventory of a company's AI estate is commercially sensitive in itself, which is why this system inherited the single-lane design rather than the routing grid of the original ticket system.

## 5. Auditability

This is the system's strongest property and the one it is really selling.

- Every step of every assessment appends to a hash chain stored with the asset.
- The chain is verified when read and reports the first broken index.
- Tested against an entry forged directly in the database: the break was reported at the exact index.
- Seeded assets carry **no** chain entries, so any chain in the system was produced by a real run.
- Measured audit completeness across the labelled benchmark: **1.0**.

## 6. Determinism

Three things must never become model calls, because the benchmark and the pack swap both depend on them: the risk roll-up, pack applicability matching, and the compliant-or-flagged decision. All three are plain code today and are covered by tests.

## 7. Cost

The GPU lane bills per warm window. Controls: a hard platform cap, a single-container lane, a single-asset switch as a cost fence before any full run, and a demonstration path whose strongest beat costs nothing.

## 8. Maintainability

This system is a fork of a fork. Several modules are near-identical to their siblings, and this repository has already been caught running an older copy of the model router than its sibling. The duplication is measured and the shared-package decision is recorded in the planning repository; until it happens, a fix in a shared-looking module must be checked in all three repositories.

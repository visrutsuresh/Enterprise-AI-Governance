# 18. Release Notes

**Version 1, 2026-07-28.** No version tags; 18 commits, from 2026-07-23 to 2026-07-27. The system was built code-complete in about a day and hardened over the following three.

## 2026-07-27, the tower gets its own face

- **Dark soft-elevation reskin.** The interface was previously indistinguishable from the sibling contract-review system, because both forked the same styling. The reskin was done by redefining a small set of design variables rather than by touching component classes, so no component changed.
- **Executive dashboard metrics** on the tower.
- Login branding and the post-login redirect corrected: both still pointed at the sibling system, which was the cause of a post-login page-not-found.
- Ports aligned with the sibling systems for the application, while keeping distinct database ports so all three stacks can run at once.
- **A full README**, which the project had been missing.
- **First live registration through the tower**, an employment-screening system: correct regulatory tier, five findings across four reviewers covering a missing bias test, no named human reviewer and no kill switch, an intact eight-entry audit chain, in about 220 seconds. Retained in the estate marked as a live registration.

## 2026-07-26, measurement

- **Full fifteen-asset benchmark committed:** all fifteen completed with zero retries and zero errors, tier accuracy 73 percent, violation recall 74 percent, flag precision 46 percent, audit completeness 1.0.

## 2026-07-25, correctness fixes shared with the sibling

- **The reasoning loop now takes the first complete JSON object** from model output. The previous parse broke deterministically whenever the model emitted a second object, and it killed the responsible-AI reviewer on both attempts at the identical character.
- **The model router gained the single-lane lock and the retry** it had been missing. This repository had been running an older copy than its sibling, which is the clearest illustration of what copy-forking costs.
- The lane credentials in this repository were blank placeholders; a benchmark run died before reaching the GPU, at no cost.

## 2026-07-24, everything else

- The nightly sweep with three additional reviewers, on-demand flag routing, and the executive brief.
- The control tower interface.
- **Live pack swap with estate-wide re-scoring**, deterministic and free: one pack produced 194 findings across 111 assets, the other 147 across 114, with 86 assets re-scored and every audit chain intact.
- The free test layer and the benchmark harness, including tests of the benchmark's own scoring.
- The demonstration script, four beats.
- **Real bug found by testing:** open-finding counts were computed from raw inspector output rather than from the canonical assessment, so estate counts would have silently frozen after any sweep or re-score.

## 2026-07-23, the pipeline

- The per-asset graph: inventory, orchestrator, a conditional fan-out to five inspectors, a plain-code fan-in, and a deterministic decision.
- The registration endpoint, which is the demonstration's hero path.
- Packs as data, with an anchored call-time loader, so a rulebook swap needs no restart.
- The 185-asset synthetic estate and a 15-asset labelled answer key with zero overlap, with seeded assets deliberately carrying empty audit chains.
- Seven read-only tools.

## Known issues carried forward

- Tier accuracy is 73 percent and at least one asset is under-rated, which is the dangerous direction of error.
- Flag precision is 46 percent against a key that was never meant to be exhaustive.
- A pack swap re-scores policy findings but not regulatory tiers, which need the model.
- The rulebook is a writable file with nothing signing or versioning it at runtime.
- There is no endpoint-level test suite here as there is in the sibling system.

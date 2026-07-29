# 18. Release Notes

**Version 1, 2026-07-28.** No version tags; 18 commits, from 2026-07-23 to 2026-07-27. The system was built code-complete in about a day and hardened over the following three.

## 2026-07-29, evidence

- **The `awaiting_evidence` column finally has something behind it.** A finding can now carry uploaded files: the screenshot of the corrected setting, the signed policy, whatever proves the work was done. Each card on the board opens to list its files and take a new one, and each file downloads by name.
- **The upload joins the hash chain**, like every other change to a finding, so the proof and the claim that the work happened sit in the same tamper-evident record.
- **Bytes went in a table, not the asset blob**, reversing the instinct from the remediation release for a stated reason (ADR-014): the blob is read in full on every estate view, and files inside it would tax every one of those reads. Only the metadata is mirrored onto the finding, which is what lets a card show its count without a second query.
- **There is no delete route, deliberately.** Evidence is an audit record; silent removal is the operation the chain exists to prevent.
- A dismissed finding refuses evidence (409), on the same reasoning that stops it being dragged. Eleven tests came with it, taking the suite from 53 to 64.

## 2026-07-28 later, remediation becomes somebody's job

- **The remediation board.** A finding now carries an owner, a due date and a status (`open`, `in_progress`, `awaiting_evidence`, `closed`, `dismissed`), stored inside the existing JSONB shape so no migration ran. A new `/remediation` screen shows the work as a four-column board with real drag and drop, filterable to mine, my team, unassigned or overdue, and the ALL view renders as dense rows because two hundred findings do not fit in columns.
- **Every change is in the chain.** Setting an owner, moving a card, changing a due date: each appends an entry to that asset's tamper-evident hash chain. Remediation state cannot change without a trace.
- **Dismissal stays a judgement.** `dismissed` is not a board column and cannot be reached by dragging; that path stays on the override verdict, which requires a written reason. A dismissed finding refuses to be revived by a drag (409). And an approved finding stays `open`, because approval is the start of remediation, not the end; the board is where approved findings land.
- The seeder now walks findings through a deterministic cycle of owners, due dates and statuses, so the board opens populated; it still writes no audit entries and never overwrites a dismissed finding.
- Nineteen endpoint tests came with it, taking the suite from 34 to 53. Two bugs were fixed on the way: the user seeder ran at import (so merely importing it needed a live database), and the demo script still named the abandoned side-by-side ports.

## 2026-07-28, the reviewer's verdict

- **Approve and override on flags.** Routing already said who should look at a flag; nothing recorded what they concluded, so a flag stayed open forever and the reviewer's judgement left no trace. `POST /flags/{id}/decision` records it: approve confirms the finding and leaves the remediation work open, override dismisses it and **requires a reason**, because a dismissal with no reason is exactly what an auditor objects to. Either verdict appends to the asset's hash chain, so the human decision sits inside the tamper-evident record rather than beside it. A flag can only be decided once.
- This matters at the measured flag precision of 46 percent: a reviewer will dismiss roughly half of what the agents raise, and until now there was nowhere to say why.
- The control tower shows the two buttons on each finding, with an inline reason box for an override and the recorded verdict afterwards.
- **Enabling fix:** the module created its database tables at import, so it could not be imported without a live Postgres, which is why this repository had no endpoint tests at all. Table creation moved into the startup hook, the same fix the ticket-triage system needed. Eight endpoint tests came with it, taking the suite from 26 to 34.

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
- Endpoint tests cover the flag-decision and remediation routes; registration, packs, sweep and the brief are still verified by hand.
- A finding update is a read-modify-write of one asset's JSON document, so concurrent edits to the same asset can clobber each other. Accepted for a two-reviewer demo estate.
- Evidence file upload (`evidence_files`) is a declared field with no upload endpoint yet.

# 15. Risk Register

**Version 1, 2026-07-28.**

## Open risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R-1 | Tier accuracy of 73 percent, with at least one asset **under-rated**, and under-rating is the dangerous direction for a governance tool | High | High | Reported openly in the benchmark and the model card. Every tier is a human's to confirm. The first quality work to resume if time allows |
| R-2 | Flag precision of 46 percent buries reviewers in flags they must dismiss | Medium | Medium | Findings carry evidence and a control id, so each is quick to judge. Not separable from genuine discovery without a second reviewer |
| R-3 | The rulebook is a writable file with nothing signing or versioning it at runtime | Medium | High | The active pack is recorded and every finding pins to a control id. Signing and change history are named as pre-production work |
| R-4 | A live demonstration runs on a cold lane | Medium | High | Warm ten minutes ahead, keep a previously registered live asset in the estate, and lead with the free pack-swap beat |
| R-5 | GPU spend exhausts the credit | Medium | Medium | Hard platform cap, one-container lane, single-asset cost fence, and a demonstration path whose strongest beat is free |
| R-6 | An asset owner describes their system flatteringly and gets a clean result | High | Medium | Unsolved by design: the system governs what it is told. Stated as the product's boundary rather than hidden |
| R-7 | Prompt injection inside a registration description | Medium | Medium | Evidence and control ids, deterministic roll-up and decision, human review of flags. Not systematically tested |
| R-8 | Duplicated modules mean a fix in a sibling never lands here | Medium, already realised once | Medium | This repository was found running an older model router than its sibling. The duplication is measured and the shared-package plan is written |
| R-9 | Every reviewer sees the whole estate | Low here, High in production | Medium | Named as a control to add before real use |
| R-10 | Documentation drifts from a fast-moving codebase | Medium | Low | Every document is dated and states what it was checked against |

## Closed risks

| # | Risk | How it closed |
|---|---|---|
| C-1 | Estate open-finding counts were computed from raw inspector output rather than the canonical assessment, so counts would have silently frozen after any sweep or re-score | Found by testing, fixed the same session |
| C-2 | A second JSON object in model output broke parsing deterministically, killing one inspector twice | The parser takes the first complete object; fixed here and in the sibling system |
| C-3 | The model router here lacked the single-lane lock and the retry its sibling had gained | The proven version was ported across |
| C-4 | The lane credentials in this repository were blank placeholders, so the first benchmark run died before reaching the GPU | Filled by hand; no money was wasted because the run died early |
| C-5 | The tamper-evidence claim was untested | Verified by forging an entry directly in the database and confirming the endpoint reported the break at the exact index |
| C-6 | The seeded estate could have made the audit demonstration meaningless | Seeded assets deliberately carry empty chains |
| C-7 | The benchmark answer key could have leaked into the estate, so retrieval would substitute for judgement | Fifteen labelled assets with zero overlap |
| C-8 | The interface was indistinguishable from the sibling contract-review system | Reskinned to a distinct dark theme by redefining a small set of design variables rather than touching components |

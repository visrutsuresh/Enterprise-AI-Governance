# Demo recordings

Screen recordings of the live app on localhost, driven end to end: both
registrations really happened, the assessment, routing, sweep and executive
brief are real model calls on the private GPU lane (Modal), and every human
action shown (override, tier correction, drag, evidence upload) was actually
performed and persisted. Agent work and long typing are fast-forwarded 10x;
the transcripts mark those moments.

- `06-governance-walkthrough.mp4` (4:49) — the whole loop in ONE CONTINUOUS
  TAKE, three sign-ins only, one per role. Lucy the reviewer: the control
  tower and its measured dashboard in a slow pan, a system registered both
  ways (form, then a paragraph an agent turns into a registry record),
  CreditLens assessed live to high risk, the four human moves on its findings
  (approve, override with a reason, agent routing watched to completion, a
  pen-test finding logged by hand), the tier corrected to unacceptable, and a
  CSV of real decisions computing fairness on the spot. Omar: the remediation
  board, where the pen-test finding gets an owner, moves to in progress by
  drag, takes its evidence file, and closes. The administrator: the policy
  pack swapped and the estate re-scored with zero code changed, the
  agent-written executive brief, the nightly sweep, and the hash-chained audit
  trail reading CHAIN INTACT before the closing tower.
  `06-governance-walkthrough-transcript.md` has narration with timestamps.
- `clips/` — the same journey as eight standalone chapters (recorded
  separately, each with its own transcript), kept for slide embeds:
  `06a-control-tower`, `06b-register-two-ways`, `06c-assessment`,
  `06d-human-judgment`, `06e-tier-and-measurement`, `06f-remediation-board`,
  `06g-packs-brief-sweep`, `06h-audit-and-close`.

Every recording passed a frame-by-frame check against its narration before
shipping; the beat-by-beat log, including the retakes it forced, is in
`VERIFICATION.md`.

Rebuild: `demo-media-kit/cap/` in the ascendion-internship repo (recorder
scripts `clip-06-full.json` / `clip-06*.json`, `record2.js`, `edit.py`,
`combine.py`).

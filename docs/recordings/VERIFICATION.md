# Recording verification log

Every take passed a frame-level gate before shipping: one frame extracted per
narration beat (`demo-media-kit/cap/check_frames.py` in the
ascendion-internship repo), each frame read against the narration line and the
database. Nothing is seeded: both registrations, the assessment, the routing
agent, the sweep and the brief are live model calls, and demo state from
failed takes is deleted (never edited) before a fresh take.

## Single-take walkthrough — three RETAKES, then PASS

**Takes 1 and 2: FAIL at "Log it".** The pen-test finding's Log it button
timed out. Take 2 ruled out scroll position (the tier-correction Save, fixed
by an up-scroll, passed). **Take 3: FAIL again** with a force-click that
fired and was swallowed. Root cause, found by probing the live page: the
"Route to a team" agent call holds the page's busy flag until its HTTP request
returns (a real model call, tens of seconds), and the take's wait matched
"Routed to" text that already existed, so the script marched on while every
mutation button on the page was still disabled. The chapter take had simply
had a faster route. Fix: the recorder gained a `waitGone` step; the take now
waits for the "Routing..." label to appear and then disappear, which is the
routing agent genuinely finishing, before touching anything else. The
log-issue form is also filled instantly (it is reset by the page's poll
re-render if typed slowly), with the narration saying so.

**Take 4 (the shipped video): PASS on all 58 beats.** DB cross-check for
CreditLens `AI-19fc1ca9`: 6 pipeline findings plus the human-logged pen test;
tier override high → unacceptable by lucy with the written reason; the pen
test finding's remediation chain owner-set → in_progress → evidence
(pen-test-evidence.txt) → closed, all by omar; pack swap and sweep entries in
the audit chain. Key beats:

| Beat | Frame shows | Verdict |
|---|---|---|
| Control tower | 189 assets / 125 with open flags / 3 unacceptable / 46 high — exactly the narrated numbers; measured executive dashboard in the slow pan; live "fraud" filter (29 of 189). | PASS |
| Register, form door | All nine fields on camera, "Register and score", no-model-call notice. | PASS |
| Register, describe door | The CreditLens paragraph, "Register and assess", "Registered. The assessment narrates below as it runs.", register ticks 189 → 191. | PASS |
| Assessment | Record page narrates the run, lands HIGH RISK with 6 findings (5 serious); the record extracted field by field (name, owner Sarah Lim, on-prem Singapore, monthly spot-check oversight). | PASS |
| Four human moves | "Confirmed by lucy" on the approved finding; "Overridden by lucy" with the written reason; "Routing..." then "Routed to risk" (the agent call watched to completion); Findings (6) → (7) with `finding_logged` on the trail. | PASS |
| Tier + measurement | UNACCEPTABLE RISK chip with `tier_override` on the trail; CSV computes DIR 0.400 BREACH, per-group approval table, n=16, `measurement` on the trail. | PASS |
| Remediation board | Header counts on camera; pen-test finding assigned (unassigned 222 → 221), dragged to IN PROGRESS, EVIDENCE 1 attached, CLOSED. | PASS |
| Packs / brief / sweep | "Pack swapped to globex-v1: 91 assets re-scored, zero code changed."; the agent-written brief paragraph; "Sweep done: 10 monitored, 6 new finding(s)" with the overnight report and the drift tile moving 14 → 20; pack swapped back. | PASS |
| Audit + close | Audit trail chip **CHAIN INTACT**, the numbered hash chain holding every pipeline step, decision, routing, logged finding, tier override, measurement and remediation from this very take; closing tower with the moved tiles. | PASS |

Retake residue (assets, evidence, measurements from failed takes) was deleted
from the database before each fresh take; nothing was patched in place.

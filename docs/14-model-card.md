# 14. Model Card

**Version 1, 2026-07-28.**

## 1. The model

| Property | Value |
|---|---|
| Model | Qwen2.5-14B-Instruct, 4-bit quantised with bitsandbytes |
| Serving | One-at-a-time transformers generation on a single GPU container. An AWQ + vLLM lane ran from 2026-07-28 to 2026-07-29 and was rolled back after the sibling system measured a recall loss on the shared lane (ADR-009 amendment) |
| Host | Serverless GPU, single container, short warm window |
| Lanes | **One.** No cloud model, no tier switch, no fallback |
| Embeddings | A small local model, cache pinned inside the repository |
| Sampling | Greedy, for reproducibility |
| Deployment | Shared with the sibling contract-review system: one endpoint, two projects |

## 2. What the model is asked to do

| Agent | Output contract |
|---|---|
| Inventory | A canonical asset record from a paragraph of prose |
| Orchestrator | Which of the five inspectors apply to this asset |
| Policy compliance | Findings against the active policy pack, each pinned to a rule |
| Risk assessment | The regulatory risk tier, plus risk findings |
| Data governance | Findings on data used, basis, and retention |
| Responsible AI | Findings on fairness, bias testing, transparency, human oversight |
| Security and third party | Findings on supply chain, third-party services, access |
| Model monitoring, regulatory intelligence, audit reporting | Sweep-time findings over a slice of the estate |

What the model is **not** asked to do: score the risk, decide compliant or flagged, or decide which policy rules apply. All three are plain code.

## 3. Measured behaviour

From the fifteen-asset labelled benchmark: every asset completed on the first attempt with zero errors, tier accuracy 73.3 percent, violation recall 74.3 percent, flag precision 46 percent, and audit completeness 1.0. Detail and caveats in [10-benchmark-report.md](10-benchmark-report.md).

Live: one registration produced the correct tier for an employment-screening system and five findings across four inspectors, in about 220 seconds.

## 4. Known failure modes

| Failure | How it shows | What contains it |
|---|---|---|
| **Under-rating a tier** | An asset rated high where the answer key says unacceptable | Nothing automatic. This is the most consequential error the system makes and it is reported openly rather than smoothed over |
| Over-flagging | Roughly half of flags were not in the answer key | Every finding carries evidence and a control id, so a reviewer dismisses a wrong one quickly |
| Second JSON object after the answer | A deterministic parse failure, twice at the identical character | The parser takes the first complete object |
| Truncated output | Same fingerprint | A generous token ceiling per call |
| Inconsistent capitalisation of the tier | Downstream comparisons silently fail | Lower-cased once, at fan-in |
| Cold container | First call after idle takes about a minute | Warm the lane before a demonstration |
| Self-serving registrations | An owner describes their system in flattering terms and gets a clean result | Not solved. Findings rest on the description given, and the system has no way to inspect a running model |

That last one is the honest boundary of the whole product: it governs **what it is told**, not what is actually deployed.

## 5. What is not measured

Whether a remediation is good advice. Whether a flag a reviewer dismissed was in fact real. How the model performs on assets unlike the synthetic estate, which was written by the same person who built the system.

## 6. Appropriate and inappropriate use

Appropriate: a first-pass inventory and assessment of AI assets, producing a control-referenced, tamper-evident record that a human governance function reviews.

Inappropriate: treating a clean result as assurance; using tiers for a regulatory filing without human confirmation, given 73 percent accuracy; any use where the description of an asset cannot be independently checked.

## 7. Human oversight

Every flag is a work item for a person. The system has no ability to block, disable or quarantine anything, and there is no code path that could. The decision it makes is a label, not an action.

# 01. Requirements

**Version 1, 2026-07-28.** Authoritative source: the client requirement PDF in this folder, plus the project plan in the planning repository. Evidence for every status is in [16-traceability-matrix.md](16-traceability-matrix.md).

## 1. Problem

A company ends up with dozens of AI models and agents scattered across teams. Nobody holds a single list of what exists, who owns it, what data it touches, which rules apply to it, or whether anyone ever checked. When a regulator or an executive asks, the answer takes weeks of chasing and is out of date on arrival.

## 2. What this product is

A control tower. It keeps a central inventory of every AI asset in the company, judges each one against a **swappable rulebook**, rolls the findings into a risk tier, routes flags to a human reviewer, sweeps the estate on a schedule, and keeps a tamper-evident audit trail for executive and regulatory reporting.

**Nothing is auto-blocked.** A flag is a work item for a person, never an automatic shutdown. That is a deliberate product decision, not a limitation.

## 3. Functional requirements

| ID | Requirement | Status |
|---|---|---|
| FR-1 | Register an AI asset from a plain-language description and turn it into a canonical record | MET |
| FR-2 | Hold a central inventory of the estate, queryable and filterable | MET, 185 seeded assets |
| FR-3 | Judge each asset against a policy pack and a regulatory framework pack, both of which are data rather than code | MET |
| FR-4 | Inspect assets across five dimensions: policy compliance, risk, data governance, responsible AI, and security and third parties | MET, five inspectors in parallel |
| FR-5 | Choose which inspectors apply to a given asset rather than always running all five | MET, an orchestrator agent decides, defaulting to all five |
| FR-6 | Assign a regulatory risk tier to each asset | MET, EU AI Act tiers |
| FR-7 | Roll findings into a risk level and score deterministically, never by a model | MET |
| FR-8 | Every finding must carry the control it pins to, a severity, a plain-English line, the evidence, and a remediation | MET, enforced by validation |
| FR-9 | Route a flag to a human reviewer, with no automatic blocking | MET |
| FR-10 | Swap the active rulebook and re-score the estate against the new one | MET, deterministic re-scoring, no model calls |
| FR-11 | Sweep the estate on demand: monitoring, regulatory intelligence, and audit reporting | MET |
| FR-12 | Produce an executive brief over the estate | MET |
| FR-13 | Keep a tamper-evident audit trail per asset, readable through the API | MET, verified against a forged database entry |
| FR-14 | Administer users: an administrator creates reviewer accounts; no open signup | MET |

## 4. Non-functional requirements

| ID | Requirement | Target | Status |
|---|---|---|---|
| NFR-1 | Rules are data, loaded at call time, so a pack can be swapped without a code change or a restart | Config, not code | MET |
| NFR-2 | Asset descriptions never reach a third-party model | Zero exceptions | MET by construction: one lane, no cloud client |
| NFR-3 | An assessment completes unattended | minutes | MET, measured about 220 seconds on a warm lane |
| NFR-4 | A stuck agent cannot hang an assessment | Per-node guard | MET |
| NFR-5 | The audit trail detects tampering | Detection, not prevention | MET |
| NFR-6 | Deterministic parts stay deterministic: risk roll-up and pack matching are plain code | Reproducible | MET |
| NFR-7 | Synthetic estate only, secrets outside the repository | No real corporate data | MET |
| NFR-8 | Reuse the skeleton from the two earlier systems | Module-level reuse | MET |

## 5. Out of scope

No agent or model runtime integration, so nothing is measured by watching a live system. No automatic enforcement or shutdown. No procurement, no vendor management, no incident response. No jurisdiction-specific legal advice: the framework pack encodes rules, it does not interpret them.

## 6. Known requirement gaps

- **Tier accuracy is 73 percent** on the labelled set, with one asset under-rated. Tiering is the highest-stakes judgement the system makes.
- **Flag precision is 46 percent**: roughly half the flags raised were not in the answer key. Some are genuine, some are noise, and they are not separable without a second reviewer.
- The pack swap re-scores policy findings deterministically, but **regulatory tiers do not move in the re-score**, because tiering needs the model. This is stated on the demonstration path rather than glossed over.

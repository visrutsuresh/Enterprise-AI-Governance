# Documentation set: Enterprise AI Governance

Version 1, 2026-07-28. Written against the code as it stands, not as planned.

| # | Document | What it answers |
|---|---|---|
| 01 | [Requirements](01-requirements.md) | What the system must do, numbered and testable |
| 02 | [High-Level Design](02-hld.md) | The components, the data flow, the tech choices |
| 03 | [Low-Level Design](03-lld.md) | Inside each component: nodes, agents, packs, state |
| 04 | [Data Model](04-data-model.md) | The asset record, findings, the estate, the packs |
| 05 | [API Specification](05-api-spec.md) | Every endpoint, its inputs, outputs, and status codes |
| 06 | [Decision Log (ADRs)](06-adr-log.md) | Each architectural decision, its options and consequences |
| 07 | [Configuration and Secrets](07-config-and-secrets.md) | Every environment variable and where its real value lives |
| 08 | [Runbook](08-runbook.md) | Start, stop, seed, recover, and what to do when it breaks |
| 09 | [Test Plan and Report](09-test-plan-and-report.md) | What is tested, how, and the last measured result |
| 10 | [Benchmark Report](10-benchmark-report.md) | Measured tier accuracy, recall, precision, audit completeness |
| 11 | [Non-Functional Requirements](11-nfr.md) | Performance, availability, privacy targets with numbers |
| 12 | [Security Review](12-security-review.md) | Threat model: what an attacker could try and what stops them |
| 13 | [Privacy and Data Handling](13-privacy-and-data-handling.md) | What data is touched and where it goes |
| 14 | [Model Card](14-model-card.md) | Which model, its limits, known failure modes |
| 15 | [Risk Register](15-risk-register.md) | What could sink the project and what mitigates it |
| 16 | [Traceability Matrix](16-traceability-matrix.md) | Requirement to code to test, so coverage is provable |
| 17 | [User Guide](17-user-guide.md) | How a reviewer operates the control tower |
| 18 | [Release Notes](18-release-notes.md) | What changed, in order, and what it broke |
| 19 | [Handover](19-handover.md) | Everything the next owner needs |

Also in this folder: the client requirement PDF, and [demo-script.md](demo-script.md) for the four-beat walkthrough.

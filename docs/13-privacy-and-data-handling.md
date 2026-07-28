# 13. Privacy and Data Handling

**Version 1, 2026-07-28.**

## 1. Position

The estate in this system is entirely synthetic. The design assumes real corporate data, because the inventory of a company's AI systems is sensitive even when no personal data is in it: it describes what the company runs, who owns it, what it touches, and where the gaps are.

## 2. What data the system holds

| Data | Where |
|---|---|
| The registration description, as written | The asset row, inside the state |
| The canonical asset record: name, type, owner, lifecycle, purpose, data touched, who is affected, whether a human reviews it | The asset row |
| Findings, with evidence and remediation | The asset row |
| The risk tier, risk level, and the decision | Real columns plus the state |
| Assessment summaries | The precedent collection |
| Audit chains | Inside the state |
| Account details | The accounts table, passwords hashed |

Note what is **not** here: no model weights, no training data, no production traffic, no personal data belonging to the people those AI systems affect. The system reasons about descriptions of AI assets, not about the assets themselves. That is a deliberate scope limit and it keeps the privacy surface small.

The one field that names a person is the asset owner, which is ordinary workplace directory information.

## 3. Where data flows

| Flow | Destination |
|---|---|
| Inventory, orchestration, inspection, sweep | The self-hosted model endpoint on rented GPU infrastructure |
| Embeddings for precedent search | Computed locally; nothing is sent out to be indexed |
| Storage | Local Postgres and local Weaviate |
| Pack matching and re-scoring | Entirely local, no model involved |

There is no third-party model provider anywhere in the system. The honest qualification is the same as its siblings: the lane is self-hosted but not on premises, so descriptions do travel to that endpoint over an authenticated connection.

## 4. Retention

Nothing is deleted. Assets, assessments, findings and audit chains are kept indefinitely, which is appropriate for a governance record: the value of an audit trail is that it does not disappear. There is no purge and no deletion endpoint.

For real use this would need a retention policy that distinguishes the **audit chain**, which should be immutable and long-lived, from the **asset description**, which may need correcting or removing.

## 5. Access

Two roles: reviewer and administrator. Every reviewer sees the whole estate. There is no per-team boundary, which is listed in [12-security-review.md](12-security-review.md) as a control to add before real use, since a governance estate is exactly the kind of data a company would want compartmented.

## 6. Precedent and confidentiality

Finished assessments are filed into a shared precedent collection and retrieved for later assets. Within one company that is the intended learning loop and raises no confidentiality problem, unlike the sibling contract-review system where precedent crosses client boundaries. If this were ever run as a multi-tenant service, the same boundary work would be needed here.

## 7. Gaps to close before real data

1. A retention policy separating the immutable chain from the mutable description.
2. Per-team access boundaries.
3. Encryption at rest.
4. A record of which model version assessed which asset, alongside the chain.
5. A correction path: today an incorrect asset record can only be superseded, not amended with a recorded reason.

# 06. Decision Log (Architecture Decision Records)

**Version 1, 2026-07-28.**

---

## ADR-001. Rules are data, not code

**Context.** Every company has its own governance rules, and regulations change. Encoding them in Python would mean a release for every policy change.
**Options.** Rules in code; rules in a database; rules as files loaded at call time.
**Decision.** Packs as files, loaded at call time and anchored to the code rather than the working directory, with each rule carrying a machine-readable applicability spec.
**Consequences.** Swapping the active rulebook is configuration, and because matching is deterministic the whole estate can be re-scored **without a single model call**. That is both the cheapest and the most convincing demonstration in the project. The limit is that regulatory tiers still need the model, so they do not move in a re-score, which is stated openly rather than hidden.

---

## ADR-002. Never auto-block

**Context.** A governance tool that can switch off a production system is a tool nobody will install.
**Decision.** The system flags and routes to a person. There is no blocking endpoint and no blocking code path.
**Consequences.** The product is adoptable, and the promise is verifiable by absence rather than by policy. The cost is that governance depends on humans acting on flags.

---

## ADR-003. Five inspectors, chosen per asset by an orchestrator

**Context.** Not every dimension applies to every asset. Running five reasoning agents on an asset that needs two is money spent for nothing.
**Options.** Always run all five; a fixed rule table; an orchestrator agent that decides.
**Decision.** An orchestrator agent picks the applicable inspectors, defaulting to all five when uncertain.
**Consequences.** Cheaper runs on simple assets, and the decision is recorded in the state so it can be reviewed. The cost is one more model call and one more thing that can be wrong.

---

## ADR-004. The roll-up, the matching and the decision are plain code

**Context.** If a model wrote the risk score, no benchmark number would mean anything, because the same asset could score differently twice.
**Decision.** Risk roll-up, pack applicability, and the compliant-or-flagged decision are deterministic code. Agents never write them.
**Consequences.** The measurements are reproducible and the pack swap is instant. The judgement stays with the agents; the arithmetic does not.

---

## ADR-005. Every finding pins to a control id

**Context.** A governance finding that cannot name the rule it came from is an opinion.
**Decision.** Each finding carries the policy rule or framework control it pins to, alongside evidence and a remediation, and is discarded if incomplete.
**Consequences.** The audit trail is defensible, and a reviewer can trace any flag back to a rule.

---

## ADR-006. Seeded assets carry empty audit chains

**Context.** A seeded estate with fabricated audit chains would make the tamper-evidence demonstration meaningless.
**Decision.** The seeder writes no chain entries. A chain exists only where a real assessment ran.
**Consequences.** Anything you see in an audit panel was genuinely produced by the pipeline, which is what makes the forged-entry demonstration land.

---

## ADR-007. The benchmark answer key does not overlap the estate

**Context.** If the labelled assets were also in the seeded estate, an inspector could retrieve the answer through precedent instead of judging.
**Decision.** Fifteen labelled assets, zero overlap with the 185-asset estate.
**Consequences.** Tier accuracy and violation recall measure judgement rather than retrieval.

---

## ADR-008. One model lane, no cloud

**Context.** An inventory of a company's AI estate is commercially sensitive in itself.
**Decision.** One self-hosted open-weight model, no cloud client, no tier switch, inherited from the sibling contract-review system.
**Consequences.** The privacy claim is provable by reading the code. The cost is model quality and per-wake GPU spend.

---

## ADR-009. Pin the lane to one container and serialise calls

**Context.** Five inspectors fanning out made the platform start a second billed GPU whose model was still loading, which killed runs mid-way in the sibling system.
**Decision.** Port the proven configuration: one container, a client-side lock, one retry on a stray server error.
**Consequences.** Predictable cost, no mid-run container swaps. This repository ran an older router for a while and had to have the fix ported across, which is the clearest example of the cost of copy-forking.
**Amended 2026-07-28, reverted 2026-07-29.** The lane briefly moved to vLLM with an AWQ checkpoint, batching up to 8 requests inside its one container, and the client-side lock was removed from the router here and in the sibling. It was rolled back the next day. The sibling benchmarked the swap over 13 contracts: 3.0x faster, but detection recall fell from 87.5% to 67.5% and the system produced 109 findings down to 69. Speed is not worth that in either product, so both routers went back to the lock and the lane back to bitsandbytes. The single-container pin was never the thing in question: it is the platform-side cap, not the lock, that prevents a second billed GPU.

One repair from that episode was **kept**, because it is a genuine bug fix rather than part of the swap: `_parse` now falls back to a tolerant read when the model emits Python literals (`True`) inside otherwise valid JSON. Strict JSON rejected the whole reply, so an inspector's entire answer could be discarded over one capital letter, and `temperature=0` made the retry reproduce it exactly. See the sibling's ADR-014.

---

## ADR-010. Take the first complete JSON object from model output

**Context.** Slicing from the first brace to the last broke deterministically whenever the model emitted a second object. One inspector failed both attempts at the identical character, twice.
**Decision.** Decode the first complete object with a streaming decoder.
**Consequences.** The failure class disappeared. The identical bug existed in the sibling system and was fixed there in the same session.

---

## ADR-011. Fork the existing skeleton again

**Context.** This was the third system in the family, with days rather than weeks available.
**Decision.** Fork the contract-review system, which had already forked the ticket system, and adapt.
**Consequences.** The system was code-complete in a day. The cost is a third copy of several modules, and two bugs have already had to be fixed twice. The plan to replace copies with a shared package is recorded in the planning repository.

---

## ADR-012. Remediation state lives inside the existing JSONB, not a findings table

**Context.** The remediation workflow (2026-07-28) needed owner, due date and status on every finding. The estate has one table, `assets`, with findings inside a JSONB array, and the open-finding counter and the decision endpoint already work directly on that array.
**Options.** Normalise findings into their own table; extend the JSONB shape in place.
**Decision.** Extend the JSONB shape. Four fields were added to the finding; existing findings read as unassigned and open, so no migration and no backfill ran.
**Consequences.** A five-hour backend job instead of twelve, and every existing reader kept working. The accepted cost: a finding update is a read-modify-write of one asset's JSON document, so two concurrent edits to findings on the same asset can clobber each other. Fine for two reviewers on a demo estate; documented rather than solved.

---

## ADR-013. The remediation screen is a status board, and dismissal is not a column

**Context.** Remediation work needed to be visible as work. The reference product class (VerifyWise and its peers) organises this as a board.
**Options.** Dense rows with inline status edits; a four-column status board with drag and drop; both.
**Decision.** A board with real drag and drop (dnd-kit) for the filtered views, chosen by the CEO from browser mockups, with the ALL view rendering as dense rows because 200 findings do not fit in columns. Two guards are requirements: `dismissed` is not a column and cannot be reached by dragging (dismissal stays on the override path, which requires a written reason), and a dismissed finding cannot be revived by a drag (409).
**Consequences.** The workflow reads as a product rather than an admin table, at roughly four extra hours of build cost. Drag listeners sit on a grip rather than the whole card, so the date picker inside a card does not start a drag. Every move writes an audit entry, keeping the tamper-evident chain the single story.

---

## ADR-014. Evidence files get their own table, and cannot be deleted

**Context.** `awaiting_evidence` had been a board column since 2026-07-28 with nothing behind it: there was no way to attach the proof the column was waiting for. ADR-012 had just established the opposite instinct, that finding state belongs in the existing JSONB.

**Options.** Bytes in the asset JSONB, consistent with ADR-012; a separate `evidence` table; an object store or a directory on disk with a path in the database.

**Decision.** A separate table, with only the file's metadata mirrored onto the finding. ADR-012's reasoning does not carry over: it traded a migration for small scalars that every reader wanted anyway, whereas the asset blob is read in full on every estate view and file bytes inside it would tax every one of those reads to serve a column almost nobody opens. An object store was rejected as infrastructure this project does not otherwise need, and a disk path was rejected because the demo runs on two different laptops and a database row travels with the dump.

**Consequences.** One new table and one index, created through the same `CREATE TABLE IF NOT EXISTS` seam, so an existing database picks it up on the next boot with no migration step. The mirror can in principle drift from the table; the table is declared the source of truth for content and the mirror a display convenience, which is enough because nothing rewrites either after the upload. **There is no delete route, deliberately:** evidence is an audit record, and silent removal is the exact operation the hash chain exists to make impossible. Withdrawing a file would have to be a new recorded event, not an erasure.

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

# 19. Handover

**Version 1, 2026-07-28.**

## 1. Get it running

Repository `README.md` for installation, [08-runbook.md](08-runbook.md) for daily operation. Docker, `uv`, Node, and an environment file. Note the database port is **5435**, not the sibling systems' ports, so all three stacks can run at once.

Order: containers up, seed accounts, seed the estate, seed precedent, start the API, start the tower, sign in.

## 2. Read these first

1. [02-hld.md](02-hld.md), the pipeline and the estate-wide capabilities.
2. [03-lld.md](03-lld.md) section 3, packs as data, which is the idea the whole product turns on.
3. [06-adr-log.md](06-adr-log.md), especially never-auto-block and the deterministic trio.

## 3. The five things that will surprise you

1. **The lane credentials live in the sibling repository's configuration.** Both projects share one model deployment, so a fresh clone here typically has blank placeholders and every assessment dies instantly with an invalid-address error. It costs nothing, but it looks like a serious failure.
2. **Three things must stay plain code:** the risk roll-up, pack applicability, and the compliant-or-flagged decision. Turning any of them into a model call would silently destroy both the benchmark and the free pack-swap demonstration.
3. **The tier's capitalisation is normalised exactly once, at fan-in.** Any new reader that touches the raw value will work in some runs and not others.
4. **Seeded assets have empty audit chains on purpose.** If you ever "fix" that by seeding chains, the tamper-evidence demonstration becomes meaningless.
5. **The labelled benchmark assets deliberately do not appear in the estate.** Adding them would let an inspector retrieve an answer through precedent instead of judging, and the accuracy numbers would stop meaning anything.

## 4. Where the important logic lives

| Question | File |
|---|---|
| Whether a policy rule applies to an asset | `fires()` in `app/packs.py` |
| How findings become a risk level | `risk_rollup()` in `app/state.py` |
| What makes a finding valid | `valid_finding()` in `app/state.py` |
| Which inspectors run for an asset | `orchestrate_agent` in `app/agents.py` and the conditional edge in `app/graph.py` |
| How a rulebook swap re-scores the estate | `rescore_policy()` in `app/sweep.py` |
| How an inspector thinks and uses tools | `app/agents_base.py` |
| Why the model lane locks | `app/router.py` |

## 5. Open work, in the order worth doing

1. **Tier accuracy**, currently 73 percent with at least one asset under-rated. The highest-stakes judgement the system makes.
2. **Approve and override annotations on flags**, so a reviewer's decision on a flag is recorded rather than implicit.
3. **An endpoint-level test suite**, matching the sibling contract-review system's.
4. **A test asserting asset descriptions can never reach a third party.**
5. **Signed or version-controlled packs**, with a record of who activated what and when. The rulebook is the trust anchor and today it is a writable file.
6. **Per-team access boundaries** on the estate.
7. **Extract the shared core** with the sibling systems, per the decision recorded in the planning repository.

## 6. Operational cautions

- `docker compose down -v` destroys the estate, the precedent collection and every audit chain. Re-seed afterwards.
- The compose database password is a long random string; an environment file that guesses the project name will fail authentication.
- The embedding cache is pinned inside the repository on purpose, after a temporary-directory cache corrupted itself and crashed seeding.
- Rehearse demonstrations on the free parts: the estate, the pack swap, the audit trail and the brief cost nothing; registrations cost GPU money.

## 7. Related repositories

This system is a fork of the contract-review system, which is itself a fork of the ticket-triage system. Several modules are near-identical across all three, and this repository has already been caught running an older copy of one of them. Until the shared package exists, a fix in a shared-looking module must be checked in all three.

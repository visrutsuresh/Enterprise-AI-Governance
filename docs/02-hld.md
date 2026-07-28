# 02. High-Level Design

**Version 1, 2026-07-28.**

## 1. The shape of the system

```
              Reviewer / administrator
                        |
                        v
    +------------------------------------------------+
    |  Next.js control tower (frontend/)              |
    |  estate | asset detail | flags | brief | people |
    +------------------------------------------------+
                        | HTTP + cookie session
                        v
    +------------------------------------------------+
    |  FastAPI backend (api.py)                       |
    |  register, estate, audit, packs, sweep,         |
    |  flag routing, executive brief, metrics         |
    +------------------------------------------------+
        |             |              |            |
        v             v              v            v
  +-----------+  +----------+  +-----------+  +----------+
  | Per-asset |  | Postgres |  | Weaviate  |  | Packs    |
  | pipeline  |  | assets   |  | precedent |  | as data  |
  +-----------+  +----------+  +-----------+  +----------+
        |
        v
  +--------------------------------------------+
  |  One model lane: self-hosted open-weight    |
  |  model on a serverless GPU. No cloud.       |
  +--------------------------------------------+
```

## 2. The per-asset pipeline

```
START -> inventory -> orchestrate -+-> policy_compliance   -+
                                   |-> risk_assessment      |
                                   |-> data_governance      +-> fan_in -> decide -> END
                                   |-> responsible_ai       |
                                   |-> security_third_party |
                                   +-> (nothing applicable) END
```

| Node | Model call | Responsibility |
|---|---|---|
| `inventory` | yes | Turn a plain-language registration into a canonical asset record |
| `orchestrate` | yes | Decide which of the five inspectors actually apply to this asset |
| Five inspectors | yes, with tools | Findings against the active packs, run as one parallel step |
| `fan_in` | no | Validate findings, lower-case the tier the model wrote, roll up risk deterministically |
| `decide` | no | `compliant` or `flagged`. Plain code, and never an automatic block |

## 3. Beyond one asset: the estate

Three things operate over the whole estate rather than a single asset:

| Capability | What it does |
|---|---|
| **Pack swap** | Activating a different policy pack re-scores every policy finding across the estate deterministically, with no model calls, by matching each rule's machine-readable applicability against each asset |
| **Sweep** | Three additional agents run over a slice of the estate: model monitoring, regulatory intelligence, and audit reporting |
| **Executive brief** | A roll-up over the estate for leadership |

The pack swap is the demonstration centrepiece and it costs nothing to run, because it is deterministic matching rather than reasoning.

## 4. Components

| Component | Where | Responsibility |
|---|---|---|
| Control tower | `frontend/` | Estate list, asset detail, flags, brief, people administration |
| API | `api.py` | Registration, estate queries, audit, packs, sweep, flag routing, metrics |
| Pipeline | `app/graph.py` | Nine-node graph with a conditional fan-out |
| Agents | `app/agents.py`, `app/agents_base.py` | Inventory, orchestrator, five inspectors, three sweep agents |
| Packs | `app/packs.py`, `data/policy_packs`, `data/framework_packs` | Rules as data, loaded at call time |
| Tools | `app/tools.py` | Seven read-only lookups |
| Model lane | `app/router.py` | One endpoint, one lock, one retry |
| System of record | `app/store.py` on Postgres | One row per asset plus the full state |
| Precedent | `app/precedent.py` on Weaviate | Prior assessments retrieved by similarity |
| Sweep | `app/sweep.py` | Estate-wide runs, re-scoring, estate metrics |
| Audit | `app/audit.py` | Hash chain per asset |

## 5. Flow of one registration

1. A reviewer pastes a paragraph describing an AI system.
2. The asset is parked as processing immediately, so the estate has a card to show.
3. Inventory canonicalises the description into a record: name, type, owner, lifecycle, data touched, and so on.
4. The orchestrator picks the applicable inspectors.
5. Those inspectors run in parallel against the active packs, using read-only tools.
6. Fan-in validates and rolls up; decide marks the asset compliant or flagged.
7. Flags are routed to a person. Nothing is blocked automatically.

Measured live: a registration took about 220 seconds on a warm lane, produced five findings across four inspectors, assigned the correct tier, and left an intact eight-entry audit chain.

## 6. Technology choices

The stack matches the two sibling systems: Python and FastAPI, LangGraph, Postgres, Weaviate, Next.js, and a single self-hosted model lane on serverless GPU. The one design idea that is unique here is **packs as data**: the rulebook is a file, matched by a machine-readable applicability spec, so swapping it is configuration rather than a release.

# Enterprise AI Governance

A multi-agent AI control tower. It keeps a central inventory of every AI model
and agent in the company, judges each one against a swappable rulebook, rolls the
findings up into a risk tier, routes flags to a human reviewer, and keeps a
tamper-evident audit trail for executive and regulatory reporting. Nothing is
auto-blocked: a flag is a work item for a person, never an automatic shutdown.

Use case #6 of the Ascendion internship build. It reuses the #1 support-ticket
skeleton and the #4 Papyrus patterns (one private model lane, hash-chain audit,
Weaviate precedent, fastapi-users auth).

**Assets never touch a cloud model.** There is exactly one model lane, a
self-hosted open-weight model on a Modal GPU. That is the whole privacy story,
which is why there is no `ANTHROPIC_API_KEY` or model-tier switch here.

---

## What's in the box

| Piece | Tech | What it does |
|---|---|---|
| Agent pipeline | LangGraph (`app/graph.py`) | inventory -> orchestrate -> 5 inspectors in parallel -> fan-in -> decide |
| Backend API | FastAPI (`api.py`) | register an asset, poll the estate, read the audit trail, route a flag, swap the rulebook, run a sweep |
| System of record | Postgres (`app/store.py`) | one row per asset: status/stage/risk columns plus the full state blob |
| Precedent cabinet | Weaviate (`app/precedent.py`) | past governance decisions, retrieved by similarity so later assets can cite earlier rulings |
| Model lane | Modal GPU (`app/router.py`) | one open-weight lane, no cloud fallback, by design |
| Reviewer UI | Next.js (`frontend/`) | the control tower, asset detail + audit view, packs admin, people admin |
| Audit trail | `app/audit.py` | SHA-256 hash chain over every pipeline step, verified on read |

### The five inspectors

They run in a single parallel LangGraph superstep, each writing only to reducer
keys (`findings_raw`, `inspector_reports`, `audit`):

| Inspector | Looks for |
|---|---|
| `policy_compliance` | breaches of the active company policy pack (`data/policy_packs/`) |
| `risk_assessment` | the EU AI Act risk tier (unacceptable / high / limited / minimal) |
| `data_governance` | what data the system touches, consent, retention, PII handling |
| `responsible_ai` | bias tests, fairness evidence, human oversight, transparency |
| `security_third_party` | third-party APIs, vendor exposure, supply-chain and access risk |

A finding is thrown away unseen unless it carries all of `finding_id`,
`inspector`, `control_id`, `severity`, `plain`, `evidence`, `remediation`.
Half-formed findings are never shown to a reviewer.

Two more agents run on their own clock (the nightly sweep, `app/sweep.py`):
`model_monitoring` (drift) and `regulatory_intel` (rule changes). Plus
`approval_workflow` (routes a flag to a team) and `executive_advisory` (the
estate brief).

---

## Prerequisites

- **Docker Desktop**, runs Postgres + Weaviate. Must be up before the backend.
- **uv**, Python package manager. https://docs.astral.sh/uv/
- **Node.js 18+** and npm.
- **A `.env`** in the repo root (gitignored, never committed).

> The model runs on Modal as a web endpoint, deployed separately from
> `modal_lane/llm_service.py`. You only need its URL + token in `.env`, you do
> not install Modal to run the app.
>
> **No lane yet? Deploy your own in ~10 minutes** (one-time, from any machine
> where `pip install modal` works):
> 1. `modal setup` (free account, $30/month free credit). Set a spend cap in
>    the Modal dashboard before anything else.
> 2. Pick a random token and store it as a Modal secret the service reads:
>    `modal secret create llm-lane-token LANE_TOKEN=<your-token>`
> 3. `modal deploy modal_lane/llm_service.py`. The deploy prints the endpoint URL.
> 4. Put the URL and your token into `.env` as `PRIVATE_LANE_URL` /
>    `PRIVATE_LANE_TOKEN`. The service scales to zero when idle, so a demo
>    costs cents.

### `.env` (copy from `.env.example`)

```
DATABASE_URL=postgresql://governance:<password>@127.0.0.1:5435/governance
AUTH_SECRET=...            # signs the login cookie/JWT; the app refuses to start without it
PRIVATE_LANE_URL=...       # the Modal endpoint (REQUIRED, read at import time)
PRIVATE_LANE_TOKEN=...     # shared secret for that endpoint (REQUIRED)
POLICY_PACK=acme           # which company policy to enforce (data/policy_packs/)
FRAMEWORK_PACK=eu_ai_act   # which regulation to score against (data/framework_packs/)
BRAND_NAME=Governance      # optional, shown in the UI header
BRAND_TAGLINE=             # optional
```

`DATABASE_URL`, `AUTH_SECRET`, and the two lane variables are read the moment
`app/store.py` / `app/users.py` / `app/router.py` are imported, so a missing one
is a startup crash, not a runtime surprise. `POLICY_PACK` and `FRAMEWORK_PACK`
are read at call time (the NFR-1 swap point), so changing them needs no restart.
Use `127.0.0.1`, not `localhost`, to force IPv4. Note the port is **5435**: #1
owns 5432, #4 owns 5433, and all three stacks are meant to run side by side.

---

## First-time setup

```bash
uv sync                                  # backend deps from pyproject.toml / uv.lock
docker compose up -d                     # Postgres 5435 + Weaviate 8082/50053
uv run python seed_users.py              # one admin + two reviewers (idempotent)
uv run python seed_estate.py             # loads the authored estate (data/estate/assets.json)
uv run python seed_precedent.py          # starter precedent decisions (idempotent)
cd frontend && npm install && cd ..
```

Seeded dev accounts (rotate before this is reachable by anyone else):

| Email | Password | Role |
|---|---|---|
| `admin@governance.dev` | `admin-dev-password` | admin |
| `lucy@governance.dev` | `reviewer-dev-password` | reviewer |
| `omar@governance.dev` | `reviewer-dev-password` | reviewer |

There is **no open signup**. The admin creates every account from the People page.

---

## Run it (two terminals)

**Terminal 1, backend**
```bash
docker compose up -d                     # if the DBs aren't already running
uv run uvicorn api:app --reload          # API on http://localhost:8000
```

**Terminal 2, frontend**
```bash
cd frontend
npm run dev                              # UI on http://localhost:3000
```

Open http://localhost:3000, sign in as the admin, and paste a one-paragraph
description of an AI system on the register form. The row narrates its stage
while the pipeline runs (cataloguing, choosing inspectors, inspecting, rolling
up), then flips to compliant or flagged, with plain-English findings pinned to
named rules.

### Behind a TLS-intercepting proxy (mitmproxy / corporate CA)

If your machine sets `HTTPS_PROXY`, it hijacks the localhost Weaviate gRPC calls
on port 50053 and times them out, so precedent search and `seed_precedent.py`
fail with `WeaviateGRPCUnavailableError`. Keep the proxy for external calls,
exclude localhost. Set this before the backend **and** before `seed_precedent.py`:

PowerShell:
```powershell
$env:NO_PROXY="127.0.0.1,localhost"; $env:no_grpc_proxy="127.0.0.1,localhost"
uv run uvicorn api:app --reload
```
bash:
```bash
export NO_PROXY=127.0.0.1,localhost no_grpc_proxy=127.0.0.1,localhost
uv run uvicorn api:app --reload
```

---

## Tests

```bash
uv run pytest tests -q
```

The suite covers the deterministic seams and never calls the model: the hash
chain (`test_audit`), the parallel fan-in pinning (`test_fanin`), the ReAct
loop's duplicate-call blocking (`test_react`), state shapes, provenance
(seed vs pipeline), the pack swap (`test_config_swap`), and bench scoring.

---

## Bench

`bench.py` scores the pipeline against labelled assets, reporting tier accuracy
and finding quality. Results land in `bench_governance.json`.

```bash
uv run python bench.py --only AI-9001    # ONE asset (real GPU time: always start here)
uv run python bench.py                   # the full set (not cheap)
```

---

## Ports and URLs

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| Weaviate | http://localhost:8082 (gRPC 50053) |
| Postgres | localhost:5435 (user `governance`, db `governance`) |

---

## Common gotchas

- **App won't start, `KeyError: 'DATABASE_URL'` / `'PRIVATE_LANE_URL'` / `RuntimeError: AUTH_SECRET missing`.**
  A required `.env` var is blank. `DATABASE_URL`, `AUTH_SECRET`, `PRIVATE_LANE_URL`,
  and `PRIVATE_LANE_TOKEN` are all read at import time.
- **`role "governance" does not exist` on startup.** The password in `DATABASE_URL`
  does not match `POSTGRES_PASSWORD` in `docker-compose.yml`, or a stale data volume
  was initialised with a different password. Postgres only applies those credentials
  on a first-time init against an empty volume. Fix: make the two agree, then, only if
  the volume was already initialised with the old password, wipe just this project's
  volume and re-init: `docker compose down && docker volume rm enterprise-ai-governance_pgdata && docker compose up -d`.
- **Weaviate gRPC times out, precedent search returns nothing.** An `HTTPS_PROXY` is
  routing localhost gRPC through the proxy. See the proxy section above (port 50053).
- **`precedent_search` returns an empty list on a fresh machine.** Run
  `uv run python seed_precedent.py` (the cabinet is empty after a volume wipe).
- **Register returns instantly but the row says "processing" for minutes.** Expected.
  The register call parks a row and returns, the pipeline runs in a background task.
  Per-node cap is 1200s with one retry, the whole run is abandoned at 25 minutes.
- **An assessment ends at `error`.** Deliberate: a dead run must say it died rather
  than strand at "processing". Check the backend log and register the asset again.
- **Port 5432 vs 5433 vs 5435.** This stack is on **5435** so it runs alongside #1
  (5432) and #4 (5433). A `DATABASE_URL` on the wrong port talks to the wrong project.

---

## Repo layout

```
api.py                FastAPI backend (register, estate, audit, packs, sweep, flags, brief, users)
bench.py              scores the pipeline, writes bench_governance.json
seed_users.py         one admin + two reviewers
seed_estate.py        loads the authored estate (data/estate/assets.json)
seed_precedent.py     starter precedent cabinet
docker-compose.yml    Postgres 5435 + Weaviate 8082/50053
app/
  graph.py            the LangGraph pipeline: inventory -> orchestrate -> 5 inspectors -> fan-in -> decide
  state.py            GovernanceState + the Finding shape + risk rollup
  agents.py           inventory, orchestrator, the five inspectors, sweep + advisory agents
  agents_base.py      the shared ReAct loop (blocks repeat tool calls, forces a finish)
  tools.py            the tool registry (rules read, precedent search, ...)
  packs.py            the policy/framework pack loader (the NFR-1 swap point)
  sweep.py            the nightly sweep + the deterministic pack re-score
  router.py           the single Modal model lane
  precedent.py        Weaviate precedent cabinet + embeddings
  store.py            Postgres system of record
  audit.py            hash-chain tamper-evident audit trail
  users.py            fastapi-users auth, reviewer | admin roles
  schemas.py          the user + asset record schemas
modal_lane/
  llm_service.py      the open-weight model service deployed to Modal
data/
  estate/             the authored asset inventory (seed fixtures)
  policy_packs/       company policy rulebooks (acme, ...)
  framework_packs/    regulation packs (eu_ai_act, ...)
tests/                pytest suite (no model calls)
frontend/             Next.js reviewer UI (App Router, Tailwind, TypeScript, port 3000)
```

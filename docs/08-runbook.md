# 08. Runbook

**Version 1, 2026-07-28.** Installation is in the repository `README.md`; this is for running, recovering and diagnosing.

## 1. Daily start

```bash
docker compose up -d                    # Postgres 5435 + Weaviate 8082/50053
uv run uvicorn api:app --reload         # API on :8000
cd frontend && npm run dev              # control tower on :3000
```

Behind a TLS-intercepting proxy, set the exclusions in the same shell as the backend and any seed script:

```bash
export NO_PROXY=127.0.0.1,localhost no_grpc_proxy=127.0.0.1,localhost
```

## 2. Seeding

| Command | Effect |
|---|---|
| `uv run python seed_users.py` | The administrator and reviewer accounts |
| The estate seed | 185 synthetic assets, with deliberately empty audit chains |
| The precedent seed | Fills the precedent collection |

All three are needed on a fresh machine and after any `docker compose down -v`. Embeddings are computed locally, so seeding costs nothing.

## 3. Health checks

| Check | How | Healthy answer |
|---|---|---|
| API alive | `GET /health` | ok |
| Estate loaded | The tower home | 185 asset cards |
| Sign-in | A seeded account | Reaches the tower |
| Model lane warm | A short probe | An answer in about a minute from cold |

## 4. Routine operations

| Task | How |
|---|---|
| Register an asset | Paste a paragraph on the tower; the card narrates its stages |
| Swap the rulebook | The packs screen, or the activate endpoint. Free, deterministic, instant |
| Sweep the estate | The sweep endpoint, over a slice |
| Route a flag | The flags screen. Never blocks anything |
| Read the executive brief | The brief screen |

## 5. Incidents

### Every assessment fails immediately with an invalid address

The lane variables are blank in this repository's environment file. This is the single most common failure here, because the lane really lives in the sibling repository's configuration and both projects share one deployment. It costs nothing, because the run dies before the GPU.

### An assessment hangs, then times out

The lane is cold, or a container swap happened mid-run. Each node has a bounded wall clock and one retry. Warm the lane rather than retrying cold, because every cold wake costs money.

### One inspector reports failed, the rest are fine

Expected: the assessment continues and the failure is visible. If it fails at the identical character on both attempts, that is truncated output rather than randomness.

### The estate counts look frozen after a sweep or a re-score

This was a real bug: open findings were counted from the raw inspector output rather than from the canonical assessment, so counts silently stopped moving. It is fixed; if counts ever look stale again, that is the first place to look.

### Database authentication failed

The environment file and the compose file disagree on the password. The compose password is a long random string, not the project name.

### The control tower will not start

Dependencies were installed but the launcher shims were not created. Install again.

### Precedent search returns an error observation

The collection was never seeded on this machine, or the proxy is intercepting its port.

## 6. Before a demo

Follow `demo-script.md`, four beats:

1. **Register a live asset**, so the audience sees a real assessment run and the stages narrate. Warm the lane ten minutes ahead.
2. **Open the audit trail** and show the chain, then the forged-entry detection.
3. **Swap the rulebook** and watch the estate re-score. This is free and instant, and it is the strongest beat.
4. **Show the executive brief.**

Keep a previously registered live asset in the estate as a fallback so beat one never depends on the network.

## 7. Cost discipline

Assessments cost GPU money; the pack swap, the estate views, the brief and the audit trail do not. Rehearse on the free parts.

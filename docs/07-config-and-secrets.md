# 07. Configuration and Secrets

**Version 1, 2026-07-28.**

## 1. Rules

- Real values live only in a git-ignored `.env`. The repository carries `.env.example` with blank placeholders.
- The lane URL and token are read when the model router is imported, so the API refuses to start without them.
- There is **no cloud model key**, by design.

## 2. Variables

| Name | Required | Meaning |
|---|---|---|
| `DATABASE_URL` | yes | Postgres connection string, port **5435**, user and database `governance`. Use `127.0.0.1` to force IPv4 |
| `AUTH_SECRET` | yes | Signs the session cookie |
| `PRIVATE_LANE_URL` | yes | HTTPS endpoint of the self-hosted model |
| `PRIVATE_LANE_TOKEN` | yes | Shared secret for that endpoint |
| Active policy pack | no | Which policy pack is live; switched through the API rather than by hand |
| Active framework pack | no | Which regulatory framework pack is live |
| `BRAND_NAME`, `BRAND_TAGLINE` | no | Branding |
| `FASTEMBED_CACHE_PATH` | no | Pinned inside the repository, after a temporary-directory embedding cache corrupted itself |

**The lane variables are shared with the sibling contract-review system**, which points at the same single deployment. A blank pair here is a known and confusing failure: an assessment dies immediately with an invalid-address error, before the GPU is ever reached, so it costs nothing but looks alarming.

## 3. Ports

| Service | Address |
|---|---|
| Control tower | http://localhost:3000 |
| API | http://localhost:8000, docs at `/docs` |
| Weaviate | http://localhost:8082, gRPC 50053 |
| Postgres | localhost:**5435** |

The data-store ports differ from both sibling systems so all three stacks can run at once. 5435 rather than the originally planned 5434, because another container already occupied that port.

## 4. Where secrets live

| Secret | Home |
|---|---|
| Lane token | The `.env` on each machine, and a platform secret on the GPU side |
| Database password | The `.env`, and it must match the compose file |
| Session secret | The `.env` |

The database password in the compose file is a long random string, not a guessable one. A common failure on a fresh machine is an environment file guessing the project's own name as the password; the two must be made to agree.

## 5. Common configuration mistakes

| Symptom | Cause |
|---|---|
| The API will not start | A lane variable or the session secret is missing |
| Every assessment fails instantly with an invalid address | The lane variables exist but are blank |
| Database authentication failed | The environment file and the compose file disagree |
| Precedent search returns errors | The proxy is intercepting the vector database's gRPC port, or the collection was never seeded |
| The web app will not launch | Dependencies installed without their launcher shims; installing again creates them |

## 6. Spend control

Every assessment wakes a rented GPU. A hard platform cap is set, the lane is capped at one container, and the benchmark has a single-asset switch used as a cost fence before any full run. The pack-swap demonstration is deliberately free.

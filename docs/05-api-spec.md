# 05. API Specification

**Version 1, 2026-07-28.** Base URL `http://localhost:8000`. A live version is served at `/docs`.

## 1. Authentication and roles

Signed cookie sessions. Two roles: `reviewer` and `admin`. **No open signup.** Every endpoint below except health and configuration requires a signed-in account.

| Method | Path | Notes |
|---|---|---|
| POST | `/auth/login` | Form credentials, returns a session cookie |
| POST | `/auth/logout` | Ends the session |
| GET | `/users/me` | The current account and role |

## 2. Public

| Method | Path | Returns |
|---|---|---|
| GET | `/`, `/health` | Health |
| GET | `/config` | Brand name and tagline |

## 3. Assets

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/assets` | reviewer or admin | Register an asset from a plain-language description. Returns immediately with an id; the assessment runs in the background |
| GET | `/assets` | reviewer or admin | The estate, with its status, stage, risk level, tier and open-finding counts |
| GET | `/assets/{id}` | reviewer or admin | The full assessment: record, findings, inspector reports, risk, decision |
| GET | `/assets/{id}/audit` | reviewer or admin | The hash chain with a verification result |

Registration is the hero path: paste a paragraph, watch the card narrate intake, orchestrating, inspecting, rolling up, done.

## 4. Packs

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/packs` | reviewer or admin | Available policy and framework packs, and which are active |
| POST | `/packs/activate` | admin | Switch the active pack and **re-score the whole estate deterministically**, with no model calls |

The re-score returns what changed: findings before and after, and how many assets were re-scored. Audit chains survive it intact.

## 5. Flags and sweep

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/flags/{finding_id}/route` | reviewer or admin | Route a flag to a person. **Never blocks the asset** |
| POST | `/sweep/run` | admin | Run the estate sweep over a slice: monitoring, regulatory intelligence, audit reporting |
| GET | `/brief` | reviewer or admin | The executive brief over the estate |
| GET | `/metrics` | reviewer or admin | Estate metrics for the dashboard |

## 6. User administration

| Method | Path | Who |
|---|---|---|
| GET | `/users` | admin |
| POST | `/users` | admin, creates a reviewer or administrator |
| DELETE | `/users/{id}` | admin, deactivates |

## 7. Status codes used

| Code | Meaning here |
|---|---|
| 200 | Success |
| 401 | No session |
| 403 | Wrong role, for example a reviewer attempting a pack swap |
| 404 | Unknown asset, finding or account |
| 409 | Duplicate account, or an action that conflicts with the current state |
| 422 | Invalid role or malformed input |

## 8. What the API deliberately does not do

There is no endpoint that blocks, disables or quarantines an asset. Routing a flag creates work for a person. That absence is the product's central promise, and it is enforced by there being no such code path at all.

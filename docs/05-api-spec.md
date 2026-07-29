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
| POST | `/flags/{finding_id}/decision` | reviewer or admin | Record what the reviewer concluded: `{verdict, reason?}` where verdict is `approved` or `overridden` |

**The decision endpoint** is the other half of routing. Routing says who should look; this says what they found.

| Verdict | Effect |
|---|---|
| `approved` | The finding is confirmed real. Its status stays `open`, because the remediation work still has to happen |
| `overridden` | The finding is dismissed. Its status becomes `dismissed` and it drops out of the estate's open-finding counts |

| Code | When |
|---|---|
| 422 | The verdict is neither `approved` nor `overridden` |
| 422 | An override was sent with no reason. **A dismissal without a reason is exactly what an auditor objects to, so it is refused** |
| 404 | No asset for that finding id, or the finding is not on its asset |
| 409 | The flag has already been decided; the first verdict stands |

Either verdict appends an entry to that asset's hash chain naming the finding, the verdict, the reviewer and the reason, so the human decision sits inside the tamper-evident record rather than beside it.

## 5a. Remediation

The remediation queue is the work-tracking half of governance: every confirmed finding is somebody's job, with an owner, a deadline and a status.

| Method | Path | Who | Notes |
|---|---|---|---|
| GET | `/remediation` | reviewer or admin | Flattens findings across the whole estate, each with its asset context (asset id, name, tier, routed team). Returns the rows plus per-status counts and overdue and unassigned totals |
| PATCH | `/flags/{finding_id}` | reviewer or admin | Sets any of `owner`, `due_at`, `status`. Sending a field set to null clears it; a field not sent is left alone. **Appends an entry to that asset's hash chain** |

Filters on `GET /remediation`, combinable:

| Filter | Means |
|---|---|
| `mine=true` | `owner` equals the signed-in account's email |
| `team=<name>` | `routed_to` equals that team name (teams exist only as routing values; accounts carry no team field) |
| `overdue=true` | `due_at` is in the past and the status is neither `closed` nor `dismissed` |
| `unassigned=true` | `owner` is null |
| `status=<word>` | Exact match on one of the five status words |

The status vocabulary is `open`, `in_progress`, `awaiting_evidence`, `closed`, `dismissed`. `PATCH` accepts only the first four (the board columns):

| Code | When |
|---|---|
| 422 | No field sent at all, a status outside the four board columns (the error points at the override path for dismissal), or a malformed `due_at` |
| 404 | No asset for that finding id, or the finding is not on its asset |
| 409 | The finding is `dismissed`. A dismissal is a recorded judgement with a reason attached; it cannot be revived by a drag |

## 5b. Evidence

The board has an `awaiting_evidence` column, and this is what it waits for: the file somebody produced to prove the remediation happened. A closed finding an auditor cannot inspect is a claim, not a control.

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/flags/{finding_id}/evidence` | reviewer or admin | Multipart upload of one file. **Appends an entry to that asset's hash chain** and mirrors the file's metadata onto the finding |
| GET | `/flags/{finding_id}/evidence` | reviewer or admin | Metadata for every file on that finding. Never returns the bytes |
| GET | `/evidence/{id}` | reviewer or admin | Downloads one file as an attachment |

Accepted types are PNG, JPEG, GIF, WebP, PDF, plain text and CSV, up to **10 MB**.

| Code | When |
|---|---|
| 400 | An unsupported content type, or an empty file |
| 413 | The file is over the 10 MB ceiling |
| 404 | No asset for that finding id, the finding is not on its asset, or no such evidence id |
| 409 | The finding is `dismissed`. Proof of work on a finding that was overridden away would tell a confusing story, so it is refused on the same reasoning as the `PATCH` route |

**There is deliberately no delete route.** Evidence is an audit record; removing it silently is precisely the operation the hash chain exists to prevent.

**The sweep and the estate views:**

| Method | Path | Who | Notes |
|---|---|---|---|
| POST | `/sweep/run` | admin | Run the estate sweep over a slice: monitoring, regulatory intelligence, audit reporting |
| GET | `/brief` | reviewer or admin | The executive brief over the estate |
| GET | `/metrics` | reviewer or admin | Estate metrics for the dashboard |

## 6. User administration

| Method | Path | Who |
|---|---|---|
| GET | `/users` | admin |
| POST | `/users` | admin, creates a reviewer or administrator |
| PATCH | `/users/{id}` | admin, edits an existing account: its email, its password, or its role. 422 if the role is neither `reviewer` nor `admin`, 404 if there is no such account, 409 if the new email is already taken |
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

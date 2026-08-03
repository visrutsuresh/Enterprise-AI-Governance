# 12. Security Review

**Version 1, 2026-07-28.** A threat model for a single-machine demonstration system that holds a map of a company's AI estate.

## 1. Assets

The inventory itself, which is commercially sensitive: what AI the company runs, who owns it, what data it touches, and where it is weak. The findings, which are a list of the company's governance failures. Account credentials, the model lane token, and the audit chains.

A list of every unpatched governance gap in an organisation is a target in its own right, which is worth saying out loud.

## 2. Trust boundaries

| Boundary | Other side |
|---|---|
| Browser to API | Anyone who can reach the port |
| API to the model lane | An internet-reachable GPU endpoint |
| API to data stores | Local Docker containers |
| Packs on disk | Whoever can write to the repository |

## 3. Threats and controls

| # | Threat | Control today | Residual risk |
|---|---|---|---|
| 1 | An outsider creates an account and reads the estate | **No open signup**; an administrator creates every account | The administrator account is a single point of trust |
| 1a | An outsider claims the founding administrator through the first-run setup route | `POST /auth/bootstrap` is unauthenticated by necessity, but it counts the accounts first and refuses with 403 the moment any exists. On a seeded or running system it is already closed | **A system that is deployed but never seeded is claimable by the first visitor.** Whoever installs it must complete setup before publishing the URL. The same applies to the sibling contract-review system |
| 2 | Password guessing | Hashed passwords | **No rate limiting or lockout** |
| 3 | Session theft | Signed cookie with a secret from the environment | Not marked secure, because the demonstration runs over plain HTTP |
| 4 | A reviewer quietly weakens the rules by editing a pack | Packs are files on disk; the active pack is recorded and every finding pins to a control id | **Nothing signs or version-controls the packs at runtime.** This is the most product-specific weakness: the rulebook is the trust anchor and it is a writable file |
| 5 | Someone edits the record to hide a finding | Hash chain per asset, verified on read, tested against a forged database row | Tamper evident, not tamper proof |
| 6 | Asset descriptions leak to a model provider | One self-hosted lane, no cloud client anywhere | Text does travel to a rented endpoint over an authenticated connection |
| 7 | The lane token is stolen and the GPU budget spent | Shared secret and a hard platform cap | The endpoint is internet reachable |
| 8 | Prompt injection inside a registration description, to suppress a finding or claim a lower tier | Findings must carry evidence and a control id, the roll-up and the decision are plain code, and a person reviews flags | **Not systematically tested.** A registration is free text written by the asset's own owner, who has an incentive to look compliant, so this is a realistic attack rather than a theoretical one |
| 9 | The system is used to switch something off | There is no blocking endpoint and no such code path | None |
| 10 | Every reviewer sees the whole estate | Two roles only | **No per-team or per-business-unit boundary** |
| 11 | Secrets committed | Only blank placeholders are committed | Nothing scans commits |

## 4. What would have to change before real use

1. Signed or version-controlled packs, with a record of who activated which pack and when.
2. Per-team access boundaries on the estate.
3. Rate limiting and lockout, HTTPS, and a secure session cookie.
4. A tested position on injection inside self-reported registrations, given that the person registering an asset benefits from a clean result.
5. Encryption at rest for the estate database.

## 5. Deliberate non-goals

No penetration test, no dependency scanning, no enforcement capability of any kind. The absence of enforcement is a product decision, not an oversight, and it removes an entire class of risk: this system cannot take anything down.

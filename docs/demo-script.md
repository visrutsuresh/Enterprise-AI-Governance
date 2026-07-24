# Demo script: the four beats

Audience takeaway: every AI system in the company is catalogued, judged against
swappable rules, and nothing about that judgement can be quietly rewritten.

## Pre-demo checklist (30 min before)

1. `docker compose up -d`, confirm `curl localhost:8082/v1/meta` answers.
2. `uv run python seed_estate.py` and `uv run python seed_precedent.py` (pristine estate).
3. WARM THE MODAL LANE (4-6 min cold): fire one small prompt through it and wait
   for a real answer. Never demo on a cold lane.
4. Run the sweep so the tower opens with overnight findings:
   `POST /sweep/run {"limit": 10}` (as admin), keep the report on screen.
5. Backend `uv run uvicorn api:app --port 8006`, frontend `npm run dev` (port 3001).
6. Log in as admin@governance.dev. Keep a psql window ready for beat 3.
7. The recorded backup of all four beats is loaded and ready to play (mandatory).

## Beat 1 - open the control tower (1 min)

~185 assets, tier tiles, overnight sweep findings, the executive brief button.
Point at the provenance badges: grey SEED = authored fixture, teal PIPELINE =
this system really ran. We never pass one off as the other.

## Beat 2 - register an asset live (3-5 min)

Paste a one-paragraph description of a deliberately naughty system (a chatbot
on a third-party API reading customer PII, nobody reviewing output). Watch the
stages narrate: cataloguing -> choosing inspectors -> inspectors at work ->
rolled up -> FLAGGED, with plain-English findings pinned to named rules.
While it runs, explain the twelve agents on their three clocks.

## Beat 3 - break the chain (2 min)

Open the asset's audit trail: green "chain intact". In psql, rewrite one entry
(the cover-up an auditor fears). Refresh: red "TAMPERED at entry N", the forged
tail highlighted. One sentence: each entry's fingerprint is computed from the
one before it, so an edit anywhere breaks every link after it.

## Beat 4 - swap the rulebook (2 min)

One click: policy pack acme -> globex. The estate re-scores in seconds, the
flag counts move (globex bans production agents, allows vetted vendors).
The point for the manager: regulation is DATA here, not code. A new law or a
new client's policy is a JSON file and an env var (NFR-1).

## If the lane misbehaves

Beat 2 is the only Modal-dependent beat. Fall back to the recording for beat 2
and keep 1, 3, 4 live (they are all $0 and local).

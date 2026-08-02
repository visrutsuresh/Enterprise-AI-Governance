"""One command builds the whole demo estate: accounts, assets, precedent.

    uv run python seed_all.py

Runs the seeds in runbook order. All idempotent, so re-running after a
partial failure is safe. Embeddings are local; seeding costs nothing.
"""

import subprocess
import sys

STEPS = [
    "seed_users.py",      # administrator and reviewer accounts
    "seed_estate.py",     # 185 synthetic assets
    "seed_precedent.py",  # precedent collection for the inspectors
]

for step in STEPS:
    print(f"\n=== {step} ===", flush=True)
    code = subprocess.run([sys.executable, step]).returncode
    if code != 0:
        sys.exit(f"\n{step} failed (exit {code}). Fix it and re-run seed_all.py, finished steps are safe to repeat.")

print("\nEstate seeded. Start the API and the frontend next.")

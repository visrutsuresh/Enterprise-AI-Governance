"""Seed the governance accounts: one admin, two reviewers. Idempotent: run any time.

The passwords below are DEVELOPMENT defaults and this repository is public, so anyone
can read them. A deployment must override them from the environment:

    SEED_ADMIN_PASSWORD=... SEED_REVIEWER_PASSWORD=... \\
    DATABASE_URL=<the deployed database> uv run python seed_users.py

Run that way against a database whose accounts already exist and it ROTATES their
passwords, which is how a leaked development credential actually gets retired.
"""
import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

import app.users as u  # noqa: E402
from app.schemas import UserCreate  # noqa: E402
from fastapi_users.exceptions import UserAlreadyExists  # noqa: E402

# development defaults, published in this public repository. Override them per
# deployment with the SEED_*_PASSWORD environment variables; see the docstring.
SEEDS = [
    ("admin@governance.dev", "admin-dev-password", "admin", True),
    ("lucy@governance.dev", "reviewer-dev-password", "reviewer", False),
    ("omar@governance.dev", "reviewer-dev-password", "reviewer", False),
]

# Per-role overrides. The literals above stay as the local-development default, so
# nothing changes on a developer machine, but a deployment can and must supply its own.
_OVERRIDES = {
    "admin": os.getenv("SEED_ADMIN_PASSWORD", "").strip(),
    "reviewer": os.getenv("SEED_REVIEWER_PASSWORD", "").strip(),
}
SEEDS = [(email, _OVERRIDES.get(role) or pw, role, su) for email, pw, role, su in SEEDS]


async def main():
    await u.create_user_table()
    async with u.session_maker() as session:
        db = u.SQLAlchemyUserDatabase(session, u.User)
        mgr = u.UserManager(db)
        for email, password, role, superuser in SEEDS:
            try:
                await mgr.create(
                    UserCreate(email=email, password=password, role=role, is_superuser=superuser)
                )
                print(f"created {email} as {role}")
            except UserAlreadyExists:
                # re-running must correct the role, and rotate the credential when an
                # override was supplied, or the published default would keep working
                existing = await db.get_by_email(email)
                patch = {"role": role}
                if _OVERRIDES.get(role):
                    # hashed explicitly, because db.update writes the column raw
                    patch["hashed_password"] = mgr.password_helper.hash(password)
                await db.update(existing, patch)
                print(f"{'rotated' if _OVERRIDES.get(role) else 'exists '} {email}")

    if not any(_OVERRIDES.values()):
        print(
            "\nNOTE: seeded with the development passwords published in this public "
            "repository. Fine locally. For any reachable deployment, set "
            "SEED_ADMIN_PASSWORD and SEED_REVIEWER_PASSWORD and run this again to rotate them."
        )


if __name__ == "__main__":
    # guarded so SEEDS can be imported (seed_estate reads the reviewer list from
    # it) without the import itself seeding accounts or needing a live database
    asyncio.run(main())

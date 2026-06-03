"""Seed script: provisions a demo user and populates that user's contacts.

Run:
    uv run python -m scripts.seed
or
    uv run python scripts/seed.py

The script talks to the FastAPI app **directly via ASGI transport** — there
is no need to start uvicorn separately. The demo user is force-confirmed
inside the database so logging in works without going through the email
verification flow.

Existing contacts with the same (email, user) pair are skipped — 409 Conflict
is treated as "already seeded".
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from sqlalchemy import update  # noqa: E402

from main import app  # noqa: E402
from src.database.db import sessionmanager  # noqa: E402
from src.database.models import User  # noqa: E402

DEMO_USER = {
    "username": "demo_user",
    "email": "demo@example.com",
    "password": "demo-password-123",
}


def _shifted(month_day_offset: int) -> str:
    target = date.today() + timedelta(days=month_day_offset)
    return target.replace(year=1990).isoformat()


SEED_CONTACTS: list[dict] = [
    {
        "first_name": "Tony",
        "last_name": "Stark",
        "email": "tony@stark.io",
        "phone": "+380501112233",
        "birthday": "1970-05-29",
        "additional_data": "Iron Man, CEO Stark Industries",
    },
    {
        "first_name": "Bruce",
        "last_name": "Banner",
        "email": "bruce@banner.io",
        "phone": "+380502223344",
        "birthday": "1969-12-18",
        "additional_data": "Hulk",
    },
    {
        "first_name": "Steve",
        "last_name": "Rogers",
        "email": "steve@avengers.org",
        "phone": "+380503334455",
        "birthday": "1918-07-04",
        "additional_data": "Captain America",
    },
    {
        "first_name": "Natasha",
        "last_name": "Romanoff",
        "email": "nat@shield.gov",
        "phone": "+380504445566",
        "birthday": _shifted(0),
        "additional_data": "Black Widow",
    },
    {
        "first_name": "Peter",
        "last_name": "Parker",
        "email": "peter@dailybugle.com",
        "phone": "+380505556677",
        "birthday": _shifted(3),
        "additional_data": "Spider-Man",
    },
    {
        "first_name": "Wanda",
        "last_name": "Maximoff",
        "email": "wanda@westview.tv",
        "phone": "+380506667788",
        "birthday": _shifted(30),
        "additional_data": "Scarlet Witch",
    },
]


async def _force_confirm(email: str) -> None:
    """Mark the demo user as email-confirmed so login() will succeed."""
    async with sessionmanager.session() as s:
        await s.execute(update(User).where(User.email == email).values(confirmed=True))
        await s.commit()


async def _register_or_get_user(client: httpx.AsyncClient) -> None:
    resp = await client.post("/auth/register", json=DEMO_USER)
    if resp.status_code == 201:
        print(f"  + registered demo user: {DEMO_USER['email']}")
    elif resp.status_code == 409:
        print(f"  = demo user already exists: {DEMO_USER['email']}")
    else:
        raise SystemExit(f"  ! unexpected {resp.status_code}: {resp.text}")
    await _force_confirm(DEMO_USER["email"])


async def _login(client: httpx.AsyncClient) -> str:
    resp = await client.post(
        "/auth/login",
        data={"username": DEMO_USER["username"], "password": DEMO_USER["password"]},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def seed() -> None:
    transport = httpx.ASGITransport(app=app)
    base = "http://testserver/api"

    async with httpx.AsyncClient(transport=transport, base_url=base) as client:
        await _register_or_get_user(client)
        token = await _login(client)
        auth_headers = {"Authorization": f"Bearer {token}"}

        created, skipped = 0, 0
        for body in SEED_CONTACTS:
            resp = await client.post("/contacts/", json=body, headers=auth_headers)
            if resp.status_code == 201:
                created += 1
                data = resp.json()
                print(
                    f"  + created id={data['id']:<3} {data['first_name']} {data['last_name']} <{data['email']}>"
                )
            elif resp.status_code == 409:
                skipped += 1
                print(f"  = skipped (already exists): {body['email']}")
            else:
                print(
                    f"  ! unexpected {resp.status_code} for {body['email']}: {resp.text}"
                )

    print()
    print(f"Seed complete. Created: {created}. Skipped (already existed): {skipped}.")


if __name__ == "__main__":
    print("Seeding contacts via FastAPI ASGI transport...\n")
    asyncio.run(seed())

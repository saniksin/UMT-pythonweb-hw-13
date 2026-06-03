"""End-to-end smoke test for the Contacts API (homework 11).

Walks every requirement from the homework spec — registration, login,
JWT-protected CRUD, tenant isolation, email verification, rate limit,
CORS preflight and avatar upload — and prints the actual HTTP request and
the corresponding response so a human can visually verify behaviour.

Steps:
    1.  Health check
    2.  Truncate users + contacts for a clean run
    3.  Register two users — duplicate email → 409, duplicate username → 409
    4.  Login before email confirmation → 401
    5.  Force-confirm both users (skip mailer) then login → JWT
    6.  CRUD without token → 401
    7.  POST 6 contacts under user A
    8.  Validation failures (422) + per-user duplicate (409)
    9.  GET list (pagination) + by-id (200/404)
    10. Search via query params
    11. PUT update + verify
    12. /contacts/birthdays — 7-day and 45-day windows
    13. DELETE + repeated DELETE → 404
    14. Tenant isolation — user B sees an empty list, cannot read A's contact
    15. /users/me — returns current user
    16. Avatar upload — patched UploadFileService → mock CDN URL
    17. CORS preflight — Access-Control-Allow-Origin in OPTIONS response
    18. Rate limit — 11th /users/me request inside one minute → 429
    19. Email confirmation flow — generate token, GET /confirmed_email/{token}

Run:
    uv run python -m scripts.smoke
or
    uv run python scripts/smoke.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402
from sqlalchemy import text, update  # noqa: E402

from main import app  # noqa: E402
from src.database.db import sessionmanager  # noqa: E402
from src.database.models import User, UserRole  # noqa: E402
from src.services.auth import create_email_token  # noqa: E402

# ──────────────────────────────────────────────────────────────────────────────
# Pretty-printing helpers
# ──────────────────────────────────────────────────────────────────────────────

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def section(title: str) -> None:
    print()
    print(f"{BOLD}{BLUE}{'═' * 78}{RESET}")
    print(f"{BOLD}{BLUE}  {title}{RESET}")
    print(f"{BOLD}{BLUE}{'═' * 78}{RESET}")


def show_request(method: str, url: str, body: Any | None = None) -> None:
    print(f"{BOLD}→ {method} {url}{RESET}")
    if body is not None:
        formatted = json.dumps(body, indent=2, ensure_ascii=False, default=str)
        for line in formatted.splitlines():
            print(f"  {DIM}{line}{RESET}")


def show_response(resp: httpx.Response, *, expect: int | None = None) -> None:
    ok = expect is None or resp.status_code == expect
    color = GREEN if ok else RED
    badge = "OK" if ok else "FAIL"
    print(f"{color}← HTTP {resp.status_code} [{badge}]{RESET}")
    try:
        body = resp.json()
    except Exception:
        body = resp.text
    if isinstance(body, (dict, list)):
        formatted = json.dumps(body, indent=2, ensure_ascii=False, default=str)
        lines = formatted.splitlines()
        if len(lines) > 30:
            print("\n".join(lines[:25]))
            print(f"  {DIM}… ({len(lines) - 25} more lines){RESET}")
        else:
            print(formatted)
    else:
        print(body)
    if not ok:
        raise AssertionError(f"Expected HTTP {expect}, got {resp.status_code}")


# ──────────────────────────────────────────────────────────────────────────────
# Test data
# ──────────────────────────────────────────────────────────────────────────────


def _shifted(offset_days: int) -> str:
    return (date.today() + timedelta(days=offset_days)).replace(year=1990).isoformat()


USER_A = {
    "username": "tony_stark",
    "email": "tony@stark.io",
    "password": "iron-man-123",
}
USER_B = {
    "username": "bruce_banner",
    "email": "bruce@banner.io",
    "password": "hulk-smash-456",
}

CONTACTS: list[dict] = [
    {
        "first_name": "Tony",
        "last_name": "Stark",
        "email": "tony@stark.io",
        "phone": "+380501112233",
        "birthday": "1970-05-29",
        "additional_data": "Iron Man",
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
        "additional_data": None,
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

# Mock CDN URL returned by the patched Cloudinary uploader.
MOCK_AVATAR_URL = "https://res.cloudinary.com/demo/image/upload/c_fill,h_250,w_250/avatar.png"


# ──────────────────────────────────────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────────────────────────────────────


async def reset_database() -> None:
    """Drop every existing user/contact so the run is reproducible.
    ``TRUNCATE … CASCADE`` clears contacts via the FK.
    """
    async with sessionmanager.session() as s:
        await s.execute(text("TRUNCATE TABLE users RESTART IDENTITY CASCADE"))
        await s.commit()


async def force_confirm(email: str) -> None:
    async with sessionmanager.session() as s:
        await s.execute(update(User).where(User.email == email).values(confirmed=True))
        await s.commit()


async def force_admin(email: str) -> None:
    """Promote a user to admin (avatar upload is admin-only)."""
    async with sessionmanager.session() as s:
        await s.execute(
            update(User).where(User.email == email).values(role=UserRole.ADMIN)
        )
        await s.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Smoke test scenario
# ──────────────────────────────────────────────────────────────────────────────


async def main() -> None:  # noqa: PLR0915
    transport = httpx.ASGITransport(app=app)
    base = "http://testserver/api"

    async with httpx.AsyncClient(transport=transport, base_url=base) as client:
        # ── 1. Health check ───────────────────────────────────────────────
        section("1. Health check")
        show_request("GET", f"{base}/healthchecker")
        show_response(await client.get("/healthchecker"), expect=200)

        # ── 2. Reset DB ───────────────────────────────────────────────────
        section("2. Reset users + contacts tables (CASCADE)")
        await reset_database()
        print(f"{GREEN}✓ tables truncated{RESET}")

        # ── 3. Registration (incl. duplicate conflicts) ───────────────────
        section("3. POST /auth/register — create users + duplicate → 409")
        show_request("POST", f"{base}/auth/register", USER_A)
        show_response(await client.post("/auth/register", json=USER_A), expect=201)

        show_request("POST", f"{base}/auth/register", USER_B)
        show_response(await client.post("/auth/register", json=USER_B), expect=201)

        dup_email = {**USER_A, "username": "different_name"}
        show_request("POST", f"{base}/auth/register", dup_email)
        show_response(await client.post("/auth/register", json=dup_email), expect=409)

        dup_username = {**USER_A, "email": "different@example.com"}
        show_request("POST", f"{base}/auth/register", dup_username)
        show_response(
            await client.post("/auth/register", json=dup_username), expect=409
        )

        # ── 4. Login before email confirmation → 401 ──────────────────────
        section("4. POST /auth/login before email confirmation → 401")
        show_request(
            "POST",
            f"{base}/auth/login",
            {"username": USER_A["username"], "password": USER_A["password"]},
        )
        show_response(
            await client.post(
                "/auth/login",
                data={
                    "username": USER_A["username"],
                    "password": USER_A["password"],
                },
            ),
            expect=401,
        )

        # ── 5. Confirm and login ──────────────────────────────────────────
        section("5. Force-confirm both users (skip mailer) and login")
        await force_confirm(USER_A["email"])
        await force_confirm(USER_B["email"])
        # USER_A becomes an admin so the admin-only avatar upload (§16) works.
        await force_admin(USER_A["email"])
        print(f"{GREEN}✓ both demo users confirmed; USER_A promoted to admin{RESET}")

        async def login(user: dict) -> str:
            show_request(
                "POST",
                f"{base}/auth/login",
                {"username": user["username"], "password": "***"},
            )
            resp = await client.post(
                "/auth/login",
                data={"username": user["username"], "password": user["password"]},
            )
            show_response(resp, expect=200)
            return resp.json()["access_token"]

        token_a = await login(USER_A)
        token_b = await login(USER_B)
        h_a = {"Authorization": f"Bearer {token_a}"}
        h_b = {"Authorization": f"Bearer {token_b}"}

        # Also verify a bad password → 401
        bad = await client.post(
            "/auth/login",
            data={"username": USER_A["username"], "password": "wrong"},
        )
        assert bad.status_code == 401
        print(f"{GREEN}✓ wrong password rejected with 401{RESET}")

        # ── 6. Anonymous CRUD → 401 ───────────────────────────────────────
        section("6. CRUD without Authorization header → 401")
        show_request("GET", f"{base}/contacts/")
        show_response(await client.get("/contacts/"), expect=401)

        show_request("POST", f"{base}/contacts/", CONTACTS[0])
        show_response(await client.post("/contacts/", json=CONTACTS[0]), expect=401)

        # ── 7. Create contacts under user A ───────────────────────────────
        section("7. POST /contacts as user A — create 6 contacts")
        created_ids: list[int] = []
        for body in CONTACTS:
            show_request("POST", f"{base}/contacts/", body)
            resp = await client.post("/contacts/", json=body, headers=h_a)
            show_response(resp, expect=201)
            created_ids.append(resp.json()["id"])

        # ── 8. Validation + duplicate ─────────────────────────────────────
        section("8. Validation (422) and per-user duplicate (409)")

        bad_email = {**CONTACTS[0], "email": "not-an-email", "phone": "+380000000001"}
        show_request("POST", f"{base}/contacts/", bad_email)
        show_response(
            await client.post("/contacts/", json=bad_email, headers=h_a), expect=422
        )

        bad_date = {
            "first_name": "X",
            "last_name": "Y",
            "email": "x@y.io",
            "phone": "+380000000002",
            "birthday": "not-a-date",
        }
        show_request("POST", f"{base}/contacts/", bad_date)
        show_response(
            await client.post("/contacts/", json=bad_date, headers=h_a), expect=422
        )

        missing = {"first_name": "OnlyName"}
        show_request("POST", f"{base}/contacts/", missing)
        show_response(
            await client.post("/contacts/", json=missing, headers=h_a), expect=422
        )

        dup_for_a = {**CONTACTS[0], "phone": "+380000000099"}
        show_request("POST", f"{base}/contacts/", dup_for_a)
        show_response(
            await client.post("/contacts/", json=dup_for_a, headers=h_a), expect=409
        )

        # ── 9. List + by-id ───────────────────────────────────────────────
        section("9. GET /contacts (limit=3) + GET /contacts/{id}")
        show_request("GET", f"{base}/contacts/?limit=3")
        show_response(
            await client.get("/contacts/", params={"limit": 3}, headers=h_a),
            expect=200,
        )

        first_id = created_ids[0]
        show_request("GET", f"{base}/contacts/{first_id}")
        show_response(
            await client.get(f"/contacts/{first_id}", headers=h_a), expect=200
        )

        show_request("GET", f"{base}/contacts/999999")
        show_response(await client.get("/contacts/999999", headers=h_a), expect=404)

        # ── 10. Search ────────────────────────────────────────────────────
        section("10. GET /contacts — search via query params")
        for params in [
            {"first_name": "tony"},
            {"last_name": "rogers"},
            {"email": "@avengers.org"},
            {"first_name": "wanda", "last_name": "stark"},
        ]:
            qs = "&".join(f"{k}={v}" for k, v in params.items())
            show_request("GET", f"{base}/contacts/?{qs}")
            resp = await client.get("/contacts/", params=params, headers=h_a)
            show_response(resp, expect=200)
            print(f"  {DIM}→ matched: {len(resp.json())} contact(s){RESET}")

        # ── 11. Update ────────────────────────────────────────────────────
        section("11. PUT /contacts/{id} — update Tony")
        updated_body = {
            **CONTACTS[0],
            "first_name": "Anthony",
            "additional_data": "Iron Man, CEO (updated)",
        }
        show_request("PUT", f"{base}/contacts/{first_id}", updated_body)
        resp = await client.put(f"/contacts/{first_id}", json=updated_body, headers=h_a)
        show_response(resp, expect=200)
        assert resp.json()["first_name"] == "Anthony"
        assert resp.json()["updated_at"] >= resp.json()["created_at"]
        print(f"  {GREEN}✓ first_name updated to 'Anthony'{RESET}")

        # ── 12. Birthdays ─────────────────────────────────────────────────
        section("12. GET /contacts/birthdays — 7-day and 45-day windows")
        show_request("GET", f"{base}/contacts/birthdays")
        resp = await client.get("/contacts/birthdays", headers=h_a)
        show_response(resp, expect=200)
        names = sorted(c["first_name"] for c in resp.json())
        assert "Natasha" in names
        assert "Peter" in names
        assert "Wanda" not in names

        show_request("GET", f"{base}/contacts/birthdays?days=45")
        resp45 = await client.get(
            "/contacts/birthdays", params={"days": 45}, headers=h_a
        )
        show_response(resp45, expect=200)
        assert any(c["first_name"] == "Wanda" for c in resp45.json())

        # ── 13. Delete + repeated delete ──────────────────────────────────
        section("13. DELETE /contacts/{id} + repeated DELETE → 404")
        target = created_ids[1]  # Bruce
        show_request("DELETE", f"{base}/contacts/{target}")
        show_response(await client.delete(f"/contacts/{target}", headers=h_a), expect=200)

        show_request("DELETE", f"{base}/contacts/{target}")
        show_response(await client.delete(f"/contacts/{target}", headers=h_a), expect=404)

        # ── 14. Tenant isolation ──────────────────────────────────────────
        section("14. Tenant isolation — user B never sees user A's data")
        show_request("GET", f"{base}/contacts/ (as user B)")
        resp = await client.get("/contacts/", headers=h_b)
        show_response(resp, expect=200)
        assert resp.json() == [], "User B must start with an empty list"
        print(f"  {GREEN}✓ user B sees empty list{RESET}")

        show_request("GET", f"{base}/contacts/{first_id} (as user B)")
        show_response(await client.get(f"/contacts/{first_id}", headers=h_b), expect=404)

        show_request("DELETE", f"{base}/contacts/{first_id} (as user B)")
        show_response(
            await client.delete(f"/contacts/{first_id}", headers=h_b), expect=404
        )
        print(f"  {GREEN}✓ user B cannot read or delete user A's contact{RESET}")

        # ── 15. /users/me ─────────────────────────────────────────────────
        section("15. GET /users/me — current user")
        show_request("GET", f"{base}/users/me")
        resp = await client.get("/users/me", headers=h_a)
        show_response(resp, expect=200)
        assert resp.json()["username"] == USER_A["username"]
        assert resp.json()["email"] == USER_A["email"]

        # ── 16. Avatar upload (Cloudinary patched) ────────────────────────
        section("16. PATCH /users/avatar — patched Cloudinary uploader")
        with patch(
            "src.api.users.UploadFileService.upload_file",
            return_value=MOCK_AVATAR_URL,
        ):
            files = {"file": ("avatar.png", b"\x89PNG\r\n\x1a\n", "image/png")}
            show_request("PATCH", f"{base}/users/avatar")
            resp = await client.patch("/users/avatar", files=files, headers=h_a)
            show_response(resp, expect=200)
            assert resp.json()["avatar"] == MOCK_AVATAR_URL
            print(f"  {GREEN}✓ avatar URL persisted: {MOCK_AVATAR_URL}{RESET}")

        # ── 17. CORS preflight ────────────────────────────────────────────
        section("17. OPTIONS preflight — CORS headers present")
        resp = await client.options(
            "/contacts/",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "authorization",
            },
        )
        show_request("OPTIONS", f"{base}/contacts/")
        print(f"{GREEN}← HTTP {resp.status_code}{RESET}")
        for k, v in resp.headers.items():
            if k.lower().startswith("access-control-"):
                print(f"  {DIM}{k}: {v}{RESET}")
        assert resp.headers.get("access-control-allow-origin") in {"*", "https://example.com"}
        print(f"  {GREEN}✓ CORS preflight allowed{RESET}")

        # ── 18. Rate limiter on /users/me ─────────────────────────────────
        section("18. /users/me — rate limit (10/min) → 429 on 11th call")
        statuses = []
        for _ in range(11):
            r = await client.get("/users/me", headers=h_a)
            statuses.append(r.status_code)
        print(f"  observed: {statuses}")
        assert statuses[-1] == 429, "11th request must be throttled"
        print(f"  {GREEN}✓ slowapi returned 429 as expected{RESET}")

        # ── 19. Email verification flow ───────────────────────────────────
        section("19. Email confirmation — generate token + GET /confirmed_email")
        # New user, this time we'll actually walk the email flow.
        third_user = {
            "username": "natasha_r",
            "email": "nat@shield.gov",
            "password": "black-widow-789",
        }
        resp = await client.post("/auth/register", json=third_user)
        if resp.status_code == 409:
            # already registered (re-run case) — just continue
            pass
        else:
            assert resp.status_code == 201, resp.text

        token = create_email_token({"sub": third_user["email"]})
        show_request("GET", f"{base}/auth/confirmed_email/<jwt>")
        resp = await client.get(f"/auth/confirmed_email/{token}")
        show_response(resp, expect=200)
        assert "confirmed" in resp.json()["message"].lower()

        # second confirmation is idempotent
        resp = await client.get(f"/auth/confirmed_email/{token}")
        show_response(resp, expect=200)

        # ── done ──────────────────────────────────────────────────────────
        section("ALL CHECKS PASSED ✓")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except AssertionError as exc:
        print(f"\n{RED}{BOLD}SMOKE FAILED: {exc}{RESET}")
        sys.exit(1)
    except Exception as exc:  # pragma: no cover
        print(f"\n{RED}{BOLD}ERROR: {exc}{RESET}")
        raise

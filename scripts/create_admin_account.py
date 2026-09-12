"""Create platform admin demo user and print credentials."""

from __future__ import annotations

import asyncio

import httpx

from initials_agent.config import get_settings
from initials_agent.saas.supabase_client import supabase_rest

EMAIL = "admin@dailycontent.demo"
PASSWORD = "AdminPass123!"


async def main() -> None:
    s = get_settings()
    base = s.supabase.url.rstrip("/")
    key = s.supabase.service_role_key.get_secret_value()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    meta = {
        "business_name": "Platform Admin",
        "positioning": "Internal platform operator account",
        "audience": "Ops",
        "offer": "",
        "cta_text": "N/A",
        "website_url": "",
        "active_niche_id": "saas_product",
        "setup_complete": True,
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{base}/auth/v1/admin/users",
            headers=headers,
            json={
                "email": EMAIL,
                "password": PASSWORD,
                "email_confirm": True,
                "user_metadata": meta,
            },
        )
        if resp.status_code in (200, 201):
            uid = str(resp.json()["id"])
        else:
            listed = await client.get(
                f"{base}/auth/v1/admin/users",
                headers=headers,
                params={"page": 1, "per_page": 200},
            )
            listed.raise_for_status()
            users = (listed.json() or {}).get("users") or []
            match = next(
                (u for u in users if (u.get("email") or "").lower() == EMAIL),
                None,
            )
            if not match:
                raise SystemExit(f"create failed: {resp.status_code} {resp.text}")
            uid = str(match["id"])
            await client.put(
                f"{base}/auth/v1/admin/users/{uid}",
                headers=headers,
                json={"password": PASSWORD, "email_confirm": True},
            )

    existing = await supabase_rest(
        "GET",
        "brands",
        params={"owner_id": f"eq.{uid}", "select": "*"},
    )
    payload = {**meta, "owner_id": uid}
    if isinstance(existing, list) and existing:
        brand_id = existing[0]["id"]
        await supabase_rest(
            "PATCH",
            "brands",
            params={"id": f"eq.{brand_id}", "select": "*"},
            json_body={k: v for k, v in payload.items() if k != "owner_id"},
            prefer="return=representation",
        )
    else:
        await supabase_rest(
            "POST",
            "brands",
            json_body=payload,
            prefer="return=representation",
        )

    print(f"email={EMAIL}")
    print(f"password={PASSWORD}")
    print(f"user_id={uid}")


if __name__ == "__main__":
    asyncio.run(main())

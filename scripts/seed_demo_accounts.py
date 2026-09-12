"""Seed a few relatable demo customer accounts into Supabase Auth + brands.

Usage (from repo root, venv on):
  python scripts/seed_demo_accounts.py

All demos use password: DemoPass123!
"""

from __future__ import annotations

import asyncio
import sys

import httpx

from initials_agent.config import get_settings
from initials_agent.saas.supabase_client import supabase_rest

DEMO_PASSWORD = "DemoPass123!"

DEMOS = [
    {
        "email": "maya@bloomroast.demo",
        "meta": {
            "business_name": "Bloom Roast Coffee",
            "positioning": "Specialty coffee subscription for busy professionals",
            "audience": "Remote workers and founders who care about ritual",
            "offer": "Monthly roasted-to-order beans + brewing tips",
            "cta_text": "Start a trial box",
            "website_url": "https://bloomroast.demo",
            "active_niche_id": "ecommerce",
            "setup_complete": True,
        },
    },
    {
        "email": "jordan@peakform.demo",
        "meta": {
            "business_name": "Peak Form Studio",
            "positioning": "Small-group strength coaching for professionals 30–45",
            "audience": "Busy professionals who want sustainable fitness",
            "offer": "8-week hybrid training programs",
            "cta_text": "Book a consult",
            "website_url": "https://peakform.demo",
            "active_niche_id": "healthtech",
            "setup_complete": True,
        },
    },
    {
        "email": "priya@northlane.demo",
        "meta": {
            "business_name": "Northlane Analytics",
            "positioning": "Product analytics for B2B SaaS without the dashboard mess",
            "audience": "SaaS PMs and growth leads",
            "offer": "Northlane Insights — weekly product opportunity briefs",
            "cta_text": "Book a demo",
            "website_url": "https://northlane.demo",
            "active_niche_id": "saas_product",
            "setup_complete": True,
        },
    },
    {
        "email": "leo@threadloom.demo",
        "meta": {
            "business_name": "Thread & Loom",
            "positioning": "Minimal everyday wear made from traceable fabrics",
            "audience": "Design-conscious shoppers 25–40",
            "offer": "Capsule wardrobe drops + care guides",
            "cta_text": "Shop the drop",
            "website_url": "https://threadloom.demo",
            "active_niche_id": "marketing_growth",
            "setup_complete": True,
        },
    },
]


async def create_or_get_user(client: httpx.AsyncClient, base: str, headers: dict, email: str, meta: dict) -> str:
    # Try create
    resp = await client.post(
        f"{base}/auth/v1/admin/users",
        headers=headers,
        json={
            "email": email,
            "password": DEMO_PASSWORD,
            "email_confirm": True,
            "user_metadata": {**meta, "setup_complete": True},
        },
    )
    if resp.status_code in (200, 201):
        uid = (resp.json() or {}).get("id")
        if uid:
            return str(uid)
    # Already exists — find by email
    list_resp = await client.get(
        f"{base}/auth/v1/admin/users",
        headers=headers,
        params={"page": 1, "per_page": 200},
    )
    list_resp.raise_for_status()
    users = (list_resp.json() or {}).get("users") or []
    for u in users:
        if (u.get("email") or "").lower() == email.lower():
            return str(u["id"])
    raise RuntimeError(f"Could not create or find user {email}: {resp.status_code} {resp.text}")


async def upsert_brand(owner_id: str, meta: dict) -> dict:
    existing = await supabase_rest(
        "GET",
        "brands",
        params={"owner_id": f"eq.{owner_id}", "select": "*"},
    )
    payload = {**meta, "owner_id": owner_id, "setup_complete": True}
    if isinstance(existing, list) and existing:
        brand_id = existing[0]["id"]
        rows = await supabase_rest(
            "PATCH",
            "brands",
            params={"id": f"eq.{brand_id}", "select": "*"},
            json_body={k: v for k, v in payload.items() if k != "owner_id"},
            prefer="return=representation",
        )
    else:
        rows = await supabase_rest(
            "POST",
            "brands",
            json_body=payload,
            prefer="return=representation",
        )
    if isinstance(rows, list) and rows:
        return rows[0]
    if isinstance(rows, dict):
        return rows
    raise RuntimeError("Brand upsert failed")


async def seed_sample_job(brand_id: str, business_name: str) -> None:
    """One sample success job so admin Overview is not empty."""
    await supabase_rest(
        "POST",
        "jobs",
        json_body={
            "brand_id": brand_id,
            "job_type": "generate",
            "status": "success",
            "payload": {"source": "seed_demo"},
            "result": {"note": f"Demo seed for {business_name}"},
        },
        prefer="return=representation",
    )


async def main() -> int:
    settings = get_settings()
    if not settings.supabase.url or not settings.supabase.service_role_key:
        print("Supabase not configured in .env", file=sys.stderr)
        return 1
    base = settings.supabase.url.rstrip("/")
    key = settings.supabase.service_role_key.get_secret_value()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    print(f"Seeding {len(DEMOS)} demo accounts…")
    print(f"Password for all: {DEMO_PASSWORD}\n")

    async with httpx.AsyncClient(timeout=30.0) as client:
        for demo in DEMOS:
            email = demo["email"]
            meta = demo["meta"]
            uid = await create_or_get_user(client, base, headers, email, meta)
            brand = await upsert_brand(uid, meta)
            try:
                await seed_sample_job(str(brand["id"]), meta["business_name"])
            except Exception as exc:
                print(f"  (job seed skipped: {exc})")
            print(f"OK  {email}")
            print(f"    brand: {meta['business_name']}  id={brand.get('id')}")
            print(f"    niche: {meta['active_niche_id']}\n")

    print("Done. Sign in as any demo email, or open Admin > Accounts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

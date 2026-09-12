"""Platform admin helpers — cross-tenant reads via Supabase service role."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from initials_agent.config import get_settings
from initials_agent.saas.supabase_client import AuthUser, supabase_rest

logger = logging.getLogger(__name__)


def admin_email_set() -> set[str]:
    raw = (get_settings().saas.admin_emails or "").strip()
    if not raw:
        return set()
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_admin_email(email: str | None) -> bool:
    if not email:
        return False
    allowed = admin_email_set()
    if not allowed:
        return False
    return email.strip().lower() in allowed


def require_admin(user: AuthUser) -> None:
    """Raise PermissionError if user is not an allowlisted admin."""
    if not is_admin_email(user.email):
        raise PermissionError("Admin access required")


async def fetch_auth_user_email(user_id: str) -> str | None:
    """Resolve owner email via Supabase Auth Admin API."""
    settings = get_settings()
    if not settings.supabase.url or not settings.supabase.service_role_key:
        return None
    url = settings.supabase.url.rstrip("/") + f"/auth/v1/admin/users/{user_id}"
    key = settings.supabase.service_role_key.get_secret_value()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers)
        if resp.is_error:
            logger.debug("Auth admin user lookup failed: %s %s", resp.status_code, resp.text)
            return None
        data = resp.json() or {}
        return data.get("email")
    except Exception as exc:
        logger.debug("Auth admin user lookup error: %s", exc)
        return None


async def list_all_brands() -> list[dict]:
    rows = await supabase_rest(
        "GET",
        "brands",
        params={"select": "*", "order": "created_at.desc"},
    )
    return rows if isinstance(rows, list) else []


async def get_brand_by_id(brand_id: str) -> dict | None:
    rows = await supabase_rest(
        "GET",
        "brands",
        params={"id": f"eq.{brand_id}", "select": "*"},
    )
    if isinstance(rows, list) and rows:
        return rows[0]
    return None


async def list_jobs(
    *,
    brand_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    params: dict[str, str] = {
        "select": "*",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if brand_id:
        params["brand_id"] = f"eq.{brand_id}"
    if status:
        params["status"] = f"eq.{status}"
    rows = await supabase_rest("GET", "jobs", params=params)
    return rows if isinstance(rows, list) else []


async def list_pipeline_runs(
    *,
    brand_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    params: dict[str, str] = {
        "select": "*",
        "order": "created_at.desc",
        "limit": str(limit),
    }
    if brand_id:
        params["brand_id"] = f"eq.{brand_id}"
    if status:
        params["status"] = f"eq.{status}"
    try:
        rows = await supabase_rest("GET", "pipeline_runs", params=params)
        return rows if isinstance(rows, list) else []
    except Exception:
        return []


async def list_drafts_for_brand(brand_id: str, limit: int = 30) -> list[dict]:
    rows = await supabase_rest(
        "GET",
        "content_drafts",
        params={
            "brand_id": f"eq.{brand_id}",
            "select": "id,title,state,created_at,updated_at,hook,cta",
            "order": "created_at.desc",
            "limit": str(limit),
        },
    )
    return rows if isinstance(rows, list) else []


async def count_drafts_for_brand(brand_id: str) -> int:
    rows = await supabase_rest(
        "GET",
        "content_drafts",
        params={"brand_id": f"eq.{brand_id}", "select": "id"},
    )
    return len(rows) if isinstance(rows, list) else 0


async def count_jobs_for_brand(brand_id: str) -> int:
    rows = await supabase_rest(
        "GET",
        "jobs",
        params={"brand_id": f"eq.{brand_id}", "select": "id"},
    )
    return len(rows) if isinstance(rows, list) else 0


async def connection_health(brand_id: str) -> list[dict]:
    """Masked social connection status — never return tokens."""
    rows = await supabase_rest(
        "GET",
        "social_connections",
        params={
            "brand_id": f"eq.{brand_id}",
            "select": "platform,account_id,author_urn,access_token_encrypted,updated_at",
        },
    )
    out: list[dict] = []
    for row in rows if isinstance(rows, list) else []:
        token = (row.get("access_token_encrypted") or "").strip()
        platform = row.get("platform") or ""
        connected = bool(token) and (
            bool(row.get("author_urn")) if platform == "linkedin" else bool(row.get("account_id"))
        )
        out.append(
            {
                "platform": platform,
                "connected": connected,
                "account_hint": (row.get("account_id") or row.get("author_urn") or "")[:24],
                "updated_at": row.get("updated_at"),
            }
        )
    return out


def _today_utc_prefix() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def admin_overview() -> dict[str, Any]:
    brands = await list_all_brands()
    jobs = await list_jobs(limit=500)
    failed_jobs = [j for j in jobs if j.get("status") == "failed"][:20]
    today = _today_utc_prefix()
    jobs_today = [j for j in jobs if str(j.get("created_at") or "").startswith(today)]

    by_status: dict[str, int] = {}
    for j in jobs:
        st = str(j.get("status") or "unknown")
        by_status[st] = by_status.get(st, 0) + 1

    today_by_status: dict[str, int] = {}
    for j in jobs_today:
        st = str(j.get("status") or "unknown")
        today_by_status[st] = today_by_status.get(st, 0) + 1

    brand_names = {str(b.get("id")): b.get("business_name") or "—" for b in brands}
    recent_failures = [
        {
            "id": j.get("id"),
            "brand_id": j.get("brand_id"),
            "brand_name": brand_names.get(str(j.get("brand_id")), "—"),
            "job_type": j.get("job_type"),
            "error": j.get("error") or (j.get("result") or {}).get("error") if isinstance(j.get("result"), dict) else j.get("error"),
            "created_at": j.get("created_at"),
            "status": j.get("status"),
            "source": "job",
        }
        for j in failed_jobs
    ]

    return {
        "brands_total": len(brands),
        "brands_setup_complete": sum(1 for b in brands if b.get("setup_complete")),
        "jobs_total": len(jobs),
        "jobs_by_status": by_status,
        "jobs_today": len(jobs_today),
        "jobs_today_by_status": today_by_status,
        "recent_failures": recent_failures,
    }


async def list_auth_users_email_map() -> dict[str, str]:
    """One Auth Admin list call → {user_id: email}. Faster than per-user lookups."""
    settings = get_settings()
    if not settings.supabase.url or not settings.supabase.service_role_key:
        return {}
    base = settings.supabase.url.rstrip("/")
    key = settings.supabase.service_role_key.get_secret_value()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    out: dict[str, str] = {}
    page = 1
    per_page = 200
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            while page <= 10:
                resp = await client.get(
                    f"{base}/auth/v1/admin/users",
                    headers=headers,
                    params={"page": page, "per_page": per_page},
                )
                if resp.is_error:
                    logger.warning("Auth users list failed: %s %s", resp.status_code, resp.text[:200])
                    break
                users = (resp.json() or {}).get("users") or []
                for u in users:
                    uid = u.get("id")
                    email = u.get("email")
                    if uid and email:
                        out[str(uid)] = str(email)
                if len(users) < per_page:
                    break
                page += 1
    except Exception as exc:
        logger.warning("Auth users list error: %s", exc)
    return out


async def _count_by_brand(table: str) -> dict[str, int]:
    """Fetch id+brand_id rows and count in memory (avoids N+1 REST calls)."""
    try:
        rows = await supabase_rest(
            "GET",
            table,
            params={"select": "brand_id", "limit": "5000"},
        )
    except Exception as exc:
        logger.warning("count_by_brand %s failed: %s", table, exc)
        return {}
    counts: dict[str, int] = {}
    for row in rows if isinstance(rows, list) else []:
        bid = str(row.get("brand_id") or "")
        if not bid:
            continue
        counts[bid] = counts.get(bid, 0) + 1
    return counts


async def admin_accounts() -> list[dict]:
    brands = await list_all_brands()
    email_map = await list_auth_users_email_map()
    draft_counts = await _count_by_brand("content_drafts")
    job_counts = await _count_by_brand("jobs")
    accounts: list[dict] = []
    for b in brands:
        oid = str(b.get("owner_id") or "")
        bid = str(b.get("id"))
        accounts.append(
            {
                "brand_id": bid,
                "business_name": b.get("business_name") or "",
                "owner_id": oid,
                "owner_email": email_map.get(oid),
                "active_niche_id": b.get("active_niche_id"),
                "setup_complete": bool(b.get("setup_complete")),
                "schedule_enabled": bool(b.get("schedule_enabled")),
                "schedule_time": b.get("schedule_time"),
                "timezone": b.get("timezone"),
                "publish_mode": b.get("publish_mode"),
                "created_at": b.get("created_at"),
                "updated_at": b.get("updated_at"),
                "draft_count": draft_counts.get(bid, 0),
                "job_count": job_counts.get(bid, 0),
            }
        )
    return accounts


async def admin_brand_detail(brand_id: str) -> dict[str, Any] | None:
    brand = await get_brand_by_id(brand_id)
    if not brand:
        return None
    oid = str(brand.get("owner_id") or "")
    email = await fetch_auth_user_email(oid) if oid else None
    jobs = await list_jobs(brand_id=brand_id, limit=30)
    runs = await list_pipeline_runs(brand_id=brand_id, limit=30)
    drafts = await list_drafts_for_brand(brand_id, limit=30)
    connections = await connection_health(brand_id)
    # Strip nothing sensitive from brand — profile fields only (no secrets on brands table)
    profile_keys = (
        "id",
        "owner_id",
        "business_name",
        "positioning",
        "audience",
        "voice_notes",
        "offer",
        "proof_points",
        "cta_text",
        "website_url",
        "active_niche_id",
        "custom_niche_text",
        "schedule_enabled",
        "schedule_time",
        "timezone",
        "publish_mode",
        "setup_complete",
        "created_at",
        "updated_at",
    )
    profile = {k: brand.get(k) for k in profile_keys}
    return {
        "profile": profile,
        "owner_email": email,
        "connections": connections,
        "jobs": jobs,
        "pipeline_runs": runs,
        "drafts": drafts,
    }


async def admin_failures(limit: int = 50) -> list[dict]:
    brands = await list_all_brands()
    brand_names = {str(b.get("id")): b.get("business_name") or "—" for b in brands}
    failed_jobs = await list_jobs(status="failed", limit=limit)
    failed_runs = await list_pipeline_runs(status="failed", limit=limit)
    items: list[dict] = []
    for j in failed_jobs:
        err = j.get("error")
        if not err and isinstance(j.get("result"), dict):
            err = j["result"].get("error")
        items.append(
            {
                "id": j.get("id"),
                "source": "job",
                "brand_id": j.get("brand_id"),
                "brand_name": brand_names.get(str(j.get("brand_id")), "—"),
                "job_type": j.get("job_type"),
                "status": j.get("status"),
                "error": err,
                "created_at": j.get("created_at"),
            }
        )
    for r in failed_runs:
        items.append(
            {
                "id": r.get("id"),
                "source": "pipeline_run",
                "brand_id": r.get("brand_id"),
                "brand_name": brand_names.get(str(r.get("brand_id")), "—"),
                "job_type": None,
                "status": r.get("status"),
                "error": (r.get("logs") or "")[:500],
                "created_at": r.get("created_at"),
            }
        )
    items.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return items[:limit]

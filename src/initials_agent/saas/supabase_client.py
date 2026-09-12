"""SaaS helpers: Supabase auth verification, cron guard, Storage uploads."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

from initials_agent.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class AuthUser:
    id: str
    email: str | None = None


def supabase_configured() -> bool:
    s = get_settings().supabase
    return bool(s.url and s.service_role_key)


def _supabase_headers(*, service: bool = True) -> dict[str, str]:
    settings = get_settings()
    key = (
        settings.supabase.service_role_key.get_secret_value()
        if service and settings.supabase.service_role_key
        else (
            settings.supabase.anon_key.get_secret_value()
            if settings.supabase.anon_key
            else ""
        )
    )
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }


async def verify_supabase_jwt(access_token: str) -> AuthUser:
    """Validate a user access token via Supabase Auth /user endpoint."""
    settings = get_settings()
    if not settings.supabase.url or not settings.supabase.anon_key:
        raise RuntimeError("Supabase is not configured (SUPABASE__URL / ANON_KEY).")
    url = settings.supabase.url.rstrip("/") + "/auth/v1/user"
    headers = {
        "apikey": settings.supabase.anon_key.get_secret_value(),
        "Authorization": f"Bearer {access_token}",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers=headers)
    if resp.status_code != 200:
        raise PermissionError("Invalid or expired session")
    data = resp.json() or {}
    uid = data.get("id")
    if not uid:
        raise PermissionError("Invalid session payload")
    return AuthUser(id=str(uid), email=data.get("email"))


def cron_secret_ok(header_value: str | None) -> bool:
    settings = get_settings()
    expected = (
        settings.saas.cron_secret.get_secret_value()
        if settings.saas.cron_secret
        else ""
    )
    if not expected:
        return False
    return (header_value or "").strip() == expected.strip()


async def supabase_rest(
    method: str,
    path: str,
    *,
    json_body: Any = None,
    params: dict | None = None,
    prefer: str | None = None,
) -> Any:
    """Minimal PostgREST call with service role."""
    settings = get_settings()
    if not settings.supabase.url or not settings.supabase.service_role_key:
        raise RuntimeError("Supabase service role is not configured.")
    base = settings.supabase.url.rstrip("/") + "/rest/v1/" + path.lstrip("/")
    headers = _supabase_headers(service=True)
    if prefer:
        headers["Prefer"] = prefer
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.request(
            method.upper(), base, headers=headers, json=json_body, params=params
        )
    if resp.is_error:
        raise RuntimeError(f"Supabase REST {method} {path} failed: {resp.status_code} {resp.text}")
    if resp.status_code == 204 or not resp.content:
        return None
    return resp.json()


async def create_job(brand_id: str, job_type: str, payload: dict | None = None) -> dict:
    rows = await supabase_rest(
        "POST",
        "jobs",
        json_body={
            "brand_id": brand_id,
            "job_type": job_type,
            "status": "queued",
            "payload": payload or {},
        },
        prefer="return=representation",
    )
    if isinstance(rows, list) and rows:
        return rows[0]
    if isinstance(rows, dict):
        return rows
    raise RuntimeError("Failed to create job row")


async def list_brands_due_for_schedule() -> list[dict]:
    """Brands with schedule_enabled=true (cron will filter by local time later)."""
    rows = await supabase_rest(
        "GET",
        "brands",
        params={"schedule_enabled": "eq.true", "select": "*"},
    )
    return rows if isinstance(rows, list) else []


async def get_brands_for_user(user_id: str) -> list[dict]:
    rows = await supabase_rest(
        "GET",
        "brands",
        params={"owner_id": f"eq.{user_id}", "select": "*"},
    )
    return rows if isinstance(rows, list) else []


async def upsert_user_brand(user_id: str, fields: dict) -> dict:
    """Create or update the user's primary brand with onboarding fields."""
    brands = await get_brands_for_user(user_id)
    payload = {k: v for k, v in fields.items() if v is not None}
    payload["setup_complete"] = True
    if brands:
        brand_id = brands[0]["id"]
        rows = await supabase_rest(
            "PATCH",
            "brands",
            params={"id": f"eq.{brand_id}", "select": "*"},
            json_body=payload,
            prefer="return=representation",
        )
    else:
        payload["owner_id"] = user_id
        if not payload.get("business_name"):
            payload["business_name"] = "My Brand"
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
    raise RuntimeError("Failed to save brand profile")


async def upload_image_bytes(
    brand_id: str,
    filename: str,
    data: bytes,
    content_type: str = "image/png",
) -> str:
    """Upload to Supabase Storage and return public URL."""
    settings = get_settings()
    if not settings.supabase.url or not settings.supabase.service_role_key:
        raise RuntimeError("Supabase is not configured for Storage uploads.")
    bucket = settings.supabase.storage_bucket or "post-images"
    path = f"{brand_id}/{filename}"
    url = (
        settings.supabase.url.rstrip("/")
        + f"/storage/v1/object/{bucket}/{path}"
    )
    key = settings.supabase.service_role_key.get_secret_value()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": content_type,
        "x-upsert": "true",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, content=data)
    if resp.is_error:
        raise RuntimeError(f"Storage upload failed: {resp.status_code} {resp.text}")
    public = (
        settings.supabase.url.rstrip("/")
        + f"/storage/v1/object/public/{bucket}/{path}"
    )
    logger.info("Uploaded image to %s", public)
    return public


async def list_storage_objects(prefix: str = "") -> list[dict]:
    """List objects in the post-images bucket (service role)."""
    settings = get_settings()
    if not settings.supabase.url or not settings.supabase.service_role_key:
        raise RuntimeError("Supabase is not configured")
    bucket = settings.supabase.storage_bucket or "post-images"
    url = settings.supabase.url.rstrip("/") + f"/storage/v1/object/list/{bucket}"
    key = settings.supabase.service_role_key.get_secret_value()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = {"prefix": prefix, "limit": 1000, "offset": 0}
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=body)
    if resp.is_error:
        raise RuntimeError(f"Storage list failed: {resp.status_code} {resp.text}")
    data = resp.json()
    return data if isinstance(data, list) else []


async def delete_storage_paths(paths: list[str]) -> None:
    """Delete object paths from the post-images bucket."""
    if not paths:
        return
    settings = get_settings()
    if not settings.supabase.url or not settings.supabase.service_role_key:
        raise RuntimeError("Supabase is not configured")
    bucket = settings.supabase.storage_bucket or "post-images"
    url = settings.supabase.url.rstrip("/") + f"/storage/v1/object/{bucket}"
    key = settings.supabase.service_role_key.get_secret_value()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.request("DELETE", url, headers=headers, json=paths)
        if resp.is_error:
            resp = await client.request(
                "DELETE", url, headers=headers, json={"prefixes": paths}
            )
        if resp.is_error:
            raise RuntimeError(f"Storage delete failed: {resp.status_code} {resp.text}")


async def clear_platform_storage(*, brand_id: str | None = None) -> dict:
    """
    Wipe Supabase Storage images and generated_assets rows.
    If brand_id is set, only that brand's folder + rows; else all.
    """
    settings = get_settings()
    bucket = settings.supabase.storage_bucket or "post-images"
    deleted_files = 0

    paths_to_delete: list[str] = []

    async def collect(prefix: str) -> None:
        objs = await list_storage_objects(prefix)
        for obj in objs:
            name = obj.get("name")
            if not name:
                continue
            full = f"{prefix}{name}" if prefix else str(name)
            # Folder entries usually have id null
            if obj.get("id") is None:
                nested_prefix = full if str(full).endswith("/") else f"{full}/"
                await collect(nested_prefix)
            else:
                paths_to_delete.append(full)

    if brand_id:
        await collect(f"{brand_id}/")
    else:
        await collect("")

    for i in range(0, len(paths_to_delete), 80):
        chunk = paths_to_delete[i : i + 80]
        await delete_storage_paths(chunk)
        deleted_files += len(chunk)

    params = {"brand_id": f"eq.{brand_id}"} if brand_id else {"id": "not.is.null"}
    deleted_rows = await supabase_rest(
        "DELETE",
        "generated_assets",
        params=params,
        prefer="return=representation",
    )
    deleted_asset_rows = len(deleted_rows) if isinstance(deleted_rows, list) else 0

    # Also wipe cloud draft-related rows so the SaaS side is clean
    cloud_cleared: dict[str, int] = {}
    for table in ("approval_requests", "content_drafts", "topics", "jobs"):
        try:
            tparams = {"brand_id": f"eq.{brand_id}"} if brand_id else {"id": "not.is.null"}
            gone = await supabase_rest(
                "DELETE",
                table,
                params=tparams,
                prefer="return=representation",
            )
            cloud_cleared[table] = len(gone) if isinstance(gone, list) else 0
        except Exception as exc:
            logger.warning("Could not clear %s: %s", table, exc)
            cloud_cleared[table] = -1

    logger.info(
        "Cleared platform storage bucket=%s files=%s assets=%s brand=%s cloud=%s",
        bucket,
        deleted_files,
        deleted_asset_rows,
        brand_id or "ALL",
        cloud_cleared,
    )
    return {
        "ok": True,
        "bucket": bucket,
        "files_deleted": deleted_files,
        "brand_id": brand_id,
        "asset_rows_cleared": deleted_asset_rows,
        "cloud_tables_cleared": cloud_cleared,
    }

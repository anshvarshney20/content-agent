"""Push local pipeline drafts + images into Supabase (Postgres + Storage)."""

from __future__ import annotations

import logging
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any

from initials_agent.config import get_settings
from initials_agent.saas.supabase_client import (
    get_brands_for_user,
    supabase_configured,
    supabase_rest,
    upload_image_bytes,
)
from initials_agent.tenant import current_user_id, tenant_db_url

logger = logging.getLogger(__name__)


async def resolve_brand_id(business_name: str | None = None) -> str | None:
    """Pick Supabase brand for the current auth user (never another tenant)."""
    settings = get_settings()
    override = (os.environ.get("SAAS__DEFAULT_BRAND_ID") or "").strip()
    uid = current_user_id()

    # Multi-tenant: always scope to the signed-in user first
    if uid and uid != "local":
        brands = await get_brands_for_user(uid)
        if brands:
            name = (business_name or "").strip().lower()
            if name:
                for b in brands:
                    if (b.get("business_name") or "").strip().lower() == name:
                        return str(b["id"])
            return str(brands[0]["id"])
        return None

    if override:
        return override

    rows = await supabase_rest("GET", "brands", params={"select": "id,business_name"})
    brands = rows if isinstance(rows, list) else []
    if not brands:
        logger.warning(
            "No Supabase brands found. Sign up once in the React app (creates a brand), "
            "or set SAAS__DEFAULT_BRAND_ID."
        )
        return None

    name = (business_name or "").strip().lower()
    if name:
        for b in brands:
            if (b.get("business_name") or "").strip().lower() == name:
                return str(b["id"])
            if name in (b.get("business_name") or "").strip().lower():
                return str(b["id"])
    return str(brands[0]["id"])


async def sync_local_draft_to_supabase(
    *,
    local_draft_id: uuid.UUID | str,
    title: str,
    hook: str,
    linkedin_post: str,
    instagram_caption: str,
    cta: str,
    hashtags: list | None,
    source_references: list | None,
    state: str,
    asset_paths: list[tuple[str, str]],
    business_name: str | None = None,
    topic_title: str | None = None,
    topic_description: str | None = None,
) -> dict[str, Any] | None:
    """
    Insert draft (+ optional topic) and upload local image files to Storage.

    asset_paths: list of (local_filesystem_path, asset_type)
    """
    if not supabase_configured():
        logger.info("Supabase not configured — skip cloud sync")
        return None

    brand_id = await resolve_brand_id(business_name)
    if not brand_id:
        return None

    topic_id = None
    if topic_title:
        topic_rows = await supabase_rest(
            "POST",
            "topics",
            json_body={
                "brand_id": brand_id,
                "title": topic_title[:500],
                "description": (topic_description or "")[:2000],
            },
            prefer="return=representation",
        )
        if isinstance(topic_rows, list) and topic_rows:
            topic_id = topic_rows[0].get("id")
        elif isinstance(topic_rows, dict):
            topic_id = topic_rows.get("id")

    draft_body = {
        "id": str(local_draft_id),
        "brand_id": brand_id,
        "topic_id": topic_id,
        "title": title,
        "hook": hook or "",
        "linkedin_post": linkedin_post or "",
        "instagram_caption": instagram_caption or "",
        "cta": cta or "",
        "hashtags": hashtags or [],
        "source_references": [str(u) for u in (source_references or [])],
        "state": state or "PENDING_APPROVAL",
    }
    draft_rows = await supabase_rest(
        "POST",
        "content_drafts",
        json_body=draft_body,
        prefer="return=representation,resolution=merge-duplicates",
    )
    # Upsert-like: if id conflict, try PATCH
    if not draft_rows:
        await supabase_rest(
            "PATCH",
            "content_drafts",
            json_body={k: v for k, v in draft_body.items() if k != "id"},
            params={"id": f"eq.{local_draft_id}"},
            prefer="return=representation",
        )

    await supabase_rest(
        "POST",
        "approval_requests",
        json_body={
            "brand_id": brand_id,
            "draft_id": str(local_draft_id),
            "status": "pending",
        },
        prefer="return=minimal",
    )

    uploaded: list[dict] = []
    for path, asset_type in asset_paths:
        public_url = await _ensure_supabase_url(brand_id, str(local_draft_id), path, asset_type)
        if not public_url:
            logger.warning("Skipping asset with no Supabase URL: %s", path)
            continue
        if not public_url.startswith("http"):
            logger.warning("Refusing to store non-HTTP asset URL in Supabase: %s", public_url)
            continue
        row = await supabase_rest(
            "POST",
            "generated_assets",
            json_body={
                "brand_id": brand_id,
                "draft_id": str(local_draft_id),
                "url": public_url,
                "storage_path": public_url,
                "asset_type": asset_type or "image",
            },
            prefer="return=representation",
        )
        if isinstance(row, list) and row:
            uploaded.append(row[0])
        elif isinstance(row, dict):
            uploaded.append(row)

    logger.info(
        "Synced draft %s to Supabase brand=%s assets=%s",
        local_draft_id,
        brand_id,
        len(uploaded),
    )
    return {
        "brand_id": brand_id,
        "draft_id": str(local_draft_id),
        "assets": uploaded,
    }


async def _ensure_supabase_url(
    brand_id: str, draft_id: str, path: str, asset_type: str
) -> str | None:
    """Return a public Supabase URL — upload from disk only if still local."""
    raw = (path or "").strip()
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return await _upload_local_file(brand_id, draft_id, raw, asset_type)


async def _upload_local_file(
    brand_id: str, draft_id: str, path: str, asset_type: str
) -> str | None:
    raw = (path or "").strip()
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    file_path = Path(raw)
    if not file_path.exists():
        name = os.path.basename(raw.replace("\\", "/"))
        candidate = Path(os.getcwd()) / "output" / "images" / name
        if candidate.exists():
            file_path = candidate
        else:
            logger.warning("Image file missing for Supabase upload: %s", raw)
            return None
    data = file_path.read_bytes()
    ext = file_path.suffix.lstrip(".") or "png"
    ctype = mimetypes.guess_type(str(file_path))[0] or "image/png"
    safe_type = (asset_type or "image").replace(" ", "_")
    filename = f"{draft_id}_{safe_type}.{ext}"
    try:
        return await upload_image_bytes(brand_id, filename, data, content_type=ctype)
    except Exception as exc:
        logger.warning("Supabase Storage upload failed (%s): %s", filename, exc)
        return None


async def backfill_local_db_images_to_supabase(limit: int = 50) -> dict[str, Any]:
    """Upload existing SQLite draft images to Supabase and rewrite local asset URLs to HTTPS."""
    from initials_agent.db.models import ContentDraftModel, GeneratedAssetModel
    from initials_agent.db.session import get_engine, get_session_factory
    from initials_agent.product.profile import load_profile

    if not supabase_configured():
        return {"ok": False, "error": "Supabase not configured"}

    brand_id = await resolve_brand_id(load_profile().business_name)
    if not brand_id:
        return {"ok": False, "error": "No Supabase brand"}

    engine = get_engine(tenant_db_url())
    session = get_session_factory(engine)()
    synced = 0
    uploaded = 0
    errors: list[str] = []
    try:
        drafts = (
            session.query(ContentDraftModel)
            .order_by(ContentDraftModel.created_at.desc())
            .limit(limit)
            .all()
        )
        for d in drafts:
            assets = session.query(GeneratedAssetModel).filter_by(draft_id=d.id).all()
            asset_paths: list[tuple[str, str]] = []
            for a in assets:
                url = str(a.url or "")
                if url.startswith("http"):
                    asset_paths.append((url, a.asset_type))
                    continue
                public = await _upload_local_file(brand_id, str(d.id), url, a.asset_type)
                if public:
                    a.url = public
                    asset_paths.append((public, a.asset_type))
                    uploaded += 1
                else:
                    errors.append(f"upload failed for {a.id}")
            try:
                await sync_local_draft_to_supabase(
                    local_draft_id=d.id,
                    title=d.title,
                    hook=d.hook or "",
                    linkedin_post=d.linkedin_post or "",
                    instagram_caption=d.instagram_caption or "",
                    cta=d.cta or "",
                    hashtags=d.hashtags or [],
                    source_references=d.source_references or [],
                    state=d.state or "PENDING_APPROVAL",
                    asset_paths=asset_paths,
                    business_name=load_profile().business_name,
                )
                synced += 1
            except Exception as exc:
                errors.append(f"draft {d.id}: {exc}")
        session.commit()
    finally:
        session.close()

    return {
        "ok": True,
        "brand_id": brand_id,
        "drafts_synced": synced,
        "images_uploaded": uploaded,
        "errors": errors[:20],
    }

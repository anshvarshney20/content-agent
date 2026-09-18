import os
import uuid
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, BackgroundTasks, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from initials_agent.config import get_settings
from initials_agent.build_id import API_BUILD
from initials_agent.db.session import get_engine, get_session_factory
from initials_agent.db.models import (
    PipelineRunModel, ContentDraftModel, ApprovalRequestModel,
    ResearchSourceModel, VisualConceptModel, GeneratedAssetModel,
    QualityCheckModel, PublishedPostModel, AnalyticsModel, StandaloneVisualModel,
    TopicModel,
)
from initials_agent.agent import DailyContentAgent, RunOptions
from initials_agent.pipeline_progress import (
    decode_progress,
    encode_progress,
    enrich_progress,
    get_live_progress,
    init_progress,
)
from initials_agent.runtime import default_topic
from initials_agent.product.profile import BrandProfile, load_profile, save_profile
from initials_agent.product.niches import NICHES
from initials_agent.repositories.approval import ApprovalRepository
from initials_agent.services.approval.local import LocalApprovalService, caption_with_hashtags
from initials_agent.tenant import (
    clear_tenant,
    cred_get,
    current_user_email,
    current_user_id,
    ensure_tenant_db,
    save_credentials,
    set_tenant,
    tenant_db_url,
)

app = FastAPI(title="Daily Content Agent API", version="1.0.0", description="Multi-brand sellable content product")

@app.on_event("startup")
def _ensure_db():
    from initials_agent.db.models import Base
    engine = get_engine(tenant_db_url())
    Base.metadata.create_all(engine)
    # In-flight rows die when the API process restarts — mark cancelled, NOT failed
    # (failed made the dashboard look like Generate was broken)
    Session = get_session_factory(engine)
    session = Session()
    try:
        stuck = session.query(PipelineRunModel).filter_by(status="running").all()
        for row in stuck:
            row.status = "cancelled"
            note = "interrupted: app/API restarted before the run finished"
            logs = (row.logs or "").strip()
            row.logs = f"{logs} | {note}" if logs else note
        if stuck:
            session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()

# Setup static files directory for images
os.makedirs(os.path.join(os.getcwd(), "output", "images"), exist_ok=True)
app.mount("/images", StaticFiles(directory=os.path.join(os.getcwd(), "output", "images")), name="images")

# CORS: prefer settings (.env SAAS__CORS_ORIGINS) so Vite ports 5173–5175 work
try:
    _cors_raw = (get_settings().saas.cors_origins or "").strip()
except Exception:
    _cors_raw = ""
if not _cors_raw:
    _cors_raw = (
        os.getenv("CORS_ORIGINS")
        or os.getenv("SAAS__CORS_ORIGINS")
        or "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174,http://127.0.0.1:5175,http://localhost:5175"
    )
_cors_origins = [o.strip() for o in _cors_raw.split(",") if o.strip()] or ["http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


_PUBLIC_API_PATHS = {
    "/api/saas/status",
    "/api/niches",
    "/api/health",
}

_hydrated_users: set[str] = set()
_jwt_cache: dict[str, tuple[float, object]] = {}


@app.middleware("http")
async def tenant_auth_middleware(request, call_next):
    """Bind every API request to the signed-in user's isolated workspace."""
    import time

    from fastapi.responses import JSONResponse
    from initials_agent.saas.supabase_client import AuthUser, supabase_configured, verify_supabase_jwt

    path = request.url.path
    if request.method == "OPTIONS" or not path.startswith("/api/"):
        return await call_next(request)
    if path in _PUBLIC_API_PATHS:
        return await call_next(request)

    try:
        if not supabase_configured():
            set_tenant("local", "local")
            ensure_tenant_db()
        else:
            auth = request.headers.get("Authorization")
            if not auth:
                return JSONResponse(status_code=401, content={"detail": "Sign in required"})
            parts = auth.split(" ", 1)
            if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
                return JSONResponse(status_code=401, content={"detail": "Expected Bearer token"})
            token = parts[1].strip()
            now = time.time()
            cached = _jwt_cache.get(token)
            if cached and cached[0] > now:
                user = cached[1]
            else:
                user = await verify_supabase_jwt(token)
                _jwt_cache[token] = (now + 90.0, user)
                if len(_jwt_cache) > 256:
                    # drop expired
                    expired = [k for k, (exp, _) in _jwt_cache.items() if exp <= now]
                    for k in expired:
                        _jwt_cache.pop(k, None)
            assert isinstance(user, AuthUser)
            set_tenant(user.id, user.email)
            ensure_tenant_db(user.id)
            if user.id not in _hydrated_users:
                await _hydrate_profile_from_cloud(user.id)
                _hydrated_users.add(user.id)
    except PermissionError as exc:
        clear_tenant()
        return JSONResponse(status_code=401, content={"detail": str(exc)})
    except Exception as exc:
        clear_tenant()
        return JSONResponse(status_code=401, content={"detail": f"Auth failed: {exc}"})

    try:
        return await call_next(request)
    finally:
        clear_tenant()


async def _hydrate_profile_from_cloud(user_id: str) -> None:
    """If this user's local workspace is empty, pull brand fields from Supabase once."""
    from initials_agent.saas.supabase_client import get_brands_for_user

    profile = load_profile()
    if profile.business_name.strip() and profile.setup_complete:
        return
    try:
        brands = await get_brands_for_user(user_id)
    except Exception:
        return
    if not brands:
        return
    b = brands[0]
    data = profile.model_dump()
    for key in (
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
    ):
        if key in b and b[key] is not None:
            data[key] = b[key]
    if data.get("business_name"):
        data["setup_complete"] = bool(data.get("setup_complete") or True)
        save_profile(BrandProfile.model_validate(data))


@app.get("/api/niches")
def list_niches():
    return {"niches": [{"id": n.id, "label": n.label} for n in NICHES]}


@app.get("/api/health")
def health():
    return {"ok": True, "api_build": API_BUILD}


def get_session():
    settings = get_settings()
    engine = get_engine(tenant_db_url())
    Session = get_session_factory(engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def build_agent(session) -> DailyContentAgent:
    from initials_agent.runtime import build_agent as _build
    return _build(session)


def _env_file_path() -> str:
    return os.path.join(os.getcwd(), ".env")


def _set_env(key: str, value: str) -> None:
    """Persist to .env and current process so settings apply without a full restart."""
    import dotenv

    env_file = _env_file_path()
    if not os.path.exists(env_file):
        open(env_file, "a", encoding="utf-8").close()
    dotenv.set_key(env_file, key, value)
    os.environ[key] = value


def _mask_secret(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if len(value) <= 12:
        return "••••••••"
    return f"{value[:8]}…{value[-4:]}"


class RunPipelineRequest(BaseModel):
    topic: Optional[str] = None
    dry_run: bool = False
    force: bool = False
    no_image: bool = False
    no_publish: bool = True

@app.get("/api/health")
def health_check():
    from initials_agent.runtime import _ai_api_key

    settings = get_settings()
    profile = load_profile()
    ai_key = _ai_api_key()
    provider = (settings.ai.provider or "openrouter").lower().strip()
    if not ai_key:
        writer = "Not configured — set AI__API_KEY"
    elif provider == "openrouter":
        writer = f"OpenRouter ({settings.ai.model_name})"
    elif provider == "openai":
        writer = f"OpenAI ({settings.ai.model_name})"
    else:
        writer = f"Unknown provider ({provider})"
    visual = "Ready" if settings.image.api_key else "Copy-only until API key is set"
    li_token = settings.linkedin.access_token.get_secret_value() if settings.linkedin.access_token else ""
    li_ok = bool(li_token and settings.linkedin.author_urn)
    ig_token = settings.instagram.access_token.get_secret_value() if settings.instagram.access_token else ""
    ig_ok = bool(ig_token and settings.instagram.account_id)
    pub = []
    if li_ok:
        pub.append("LinkedIn")
    if ig_ok:
        pub.append("Instagram")
    return {
        "status": "Active" if ai_key else "Needs AI key",
        "api_build": API_BUILD,
        "agent": "Daily Content Agent",
        "brand": profile.business_name or "Not set up",
        "niche": profile.niche_label(),
        "ai_ready": bool(ai_key),
        "modules": {
            "Daily Research": "Live RSS",
            "Content Strategist": "Ready",
            "LinkedIn + Instagram Writer": writer,
            "Visual Agent": visual,
            "Quality Control": "Ready",
            "Publishing": " + ".join(pub) if pub else "Review / copy-ready",
            "Scheduler": (
                f"{profile.schedule_time} {profile.timezone}"
                + (" (on)" if profile.schedule_enabled else " (off)")
            ),
        }
    }

@app.get("/api/profile")
def get_profile():
    profile = load_profile()
    settings = get_settings()
    from initials_agent.runtime import _ai_api_key

    uid = current_user_id()
    if uid and uid != "local":
        li_token = cred_get("linkedin_access_token")
        ig_token = cred_get("instagram_access_token")
        author_urn = cred_get("linkedin_author_urn")
        ig_account = cred_get("instagram_account_id")
        public_base = cred_get("public_base_url") or (settings.app.public_base_url or "")
        ig_loc_id = cred_get("instagram_location_id")
        ig_loc_name = cred_get("instagram_location_name")
        ai_provider = cred_get("ai_provider") or "openrouter"
        ai_model = cred_get("ai_model_name") or settings.ai.model_name
        image_provider = cred_get("image_provider") or "puter"
        image_model = cred_get("image_model_name") or settings.image.model_name
        image_key = cred_get("image_api_key")
    else:
        # Prefer local Settings credentials over .env when present
        from initials_agent.tenant import load_credentials

        local_creds = load_credentials("local")
        li_token = settings.linkedin.access_token.get_secret_value() if settings.linkedin.access_token else ""
        ig_token = settings.instagram.access_token.get_secret_value() if settings.instagram.access_token else ""
        author_urn = settings.linkedin.author_urn or ""
        ig_account = settings.instagram.account_id or ""
        public_base = settings.app.public_base_url or ""
        ig_loc_id = settings.instagram.location_id or ""
        ig_loc_name = settings.instagram.location_name or ""
        ai_provider = local_creds.get("ai_provider") or settings.ai.provider
        ai_model = local_creds.get("ai_model_name") or settings.ai.model_name
        image_provider = local_creds.get("image_provider") or settings.image.provider or "puter"
        image_model = local_creds.get("image_model_name") or settings.image.model_name
        image_key = local_creds.get("image_api_key") or (
            settings.image.api_key.get_secret_value() if settings.image.api_key else ""
        )

    # Normalize removed providers in the UI
    if str(image_provider).lower() in {"bfl", "cloudflare", "pollinations", "nvidia", "flux"}:
        image_provider = "puter"
        image_key = ""  # old keys are not Puter tokens
        image_model = image_model or "openai/gpt-image-2"
    return {
        **profile.model_dump(),
        "niche_label": profile.niche_label(),
        "research_query": profile.research_query(),
        "is_ready": profile.is_ready(),
        "account_email": current_user_email() or "",
        "ai_ready": bool(_ai_api_key()),
        "ai_model": ai_model,
        "ai_provider": ai_provider,
        "ai_key_masked": _mask_secret(_ai_api_key()),
        "image_provider": image_provider,
        "image_model": image_model,
        "image_ready": bool(image_key),
        "image_key_masked": _mask_secret(image_key),
        "niches": [{"id": n.id, "label": n.label} for n in NICHES],
        "linkedin_connected": bool(li_token and author_urn),
        "linkedin_access_token_masked": _mask_secret(li_token),
        "linkedin_author_urn": author_urn,
        "instagram_connected": bool(ig_token and ig_account),
        "instagram_access_token_masked": _mask_secret(ig_token),
        "instagram_account_id": ig_account,
        "public_base_url": public_base,
        "instagram_location_id": ig_loc_id,
        "instagram_location_name": ig_loc_name,
    }

class UpdateProfileRequest(BaseModel):
    business_name: Optional[str] = None
    positioning: Optional[str] = None
    audience: Optional[str] = None
    voice_notes: Optional[str] = None
    offer: Optional[str] = None
    proof_points: Optional[str] = None
    cta_text: Optional[str] = None
    website_url: Optional[str] = None
    active_niche_id: Optional[str] = None
    custom_niche_text: Optional[str] = None
    enabled_niche_ids: Optional[list[str]] = None
    schedule_enabled: Optional[bool] = None
    schedule_time: Optional[str] = None
    timezone: Optional[str] = None
    publish_mode: Optional[str] = None
    setup_complete: Optional[bool] = None

@app.put("/api/profile")
def put_profile(req: UpdateProfileRequest):
    profile = load_profile()
    data = profile.model_dump()
    for key, value in req.model_dump(exclude_unset=True).items():
        if value is not None:
            data[key] = value
    updated = BrandProfile.model_validate(data)
    if updated.business_name.strip() and updated.positioning.strip():
        updated.setup_complete = True if req.setup_complete is None else bool(req.setup_complete or updated.setup_complete)
    save_profile(updated)
    return {
        **updated.model_dump(),
        "niche_label": updated.niche_label(),
        "research_query": updated.research_query(),
        "is_ready": updated.is_ready(),
    }

class UpdateLinkedInRequest(BaseModel):
    access_token: str = ""
    author_urn: str


@app.post("/api/settings/linkedin")
def update_linkedin_settings(req: UpdateLinkedInRequest):
    token = (req.access_token or "").strip()
    if not token:
        token = cred_get("linkedin_access_token")
    if not token:
        raise HTTPException(status_code=400, detail="LinkedIn access token is required")
    urn = (req.author_urn or "").strip()
    if not urn:
        raise HTTPException(status_code=400, detail="LinkedIn author URN is required")
    uid = current_user_id()
    if uid and uid != "local":
        save_credentials({"linkedin_access_token": token, "linkedin_author_urn": urn})
    else:
        _set_env("LINKEDIN__ACCESS_TOKEN", token)
        _set_env("LINKEDIN__AUTHOR_URN", urn)
    return {
        "status": "success",
        "linkedin_connected": True,
        "linkedin_access_token_masked": _mask_secret(token),
    }

class UpdateInstagramRequest(BaseModel):
    access_token: str = ""
    account_id: str
    public_base_url: str
    location_id: Optional[str] = None
    location_name: Optional[str] = None

@app.post("/api/settings/instagram")
def update_instagram_settings(req: UpdateInstagramRequest):
    token = (req.access_token or "").strip()
    if not token:
        token = cred_get("instagram_access_token")
    if not token:
        raise HTTPException(status_code=400, detail="Instagram access token is required")
    account = (req.account_id or "").strip()
    if not account:
        raise HTTPException(status_code=400, detail="Instagram account id is required")
    loc_id = (req.location_id or "").strip()
    loc_name = (req.location_name or "").strip()
    public_base = req.public_base_url.strip().rstrip("/")
    uid = current_user_id()
    if uid and uid != "local":
        save_credentials(
            {
                "instagram_access_token": token,
                "instagram_account_id": account,
                "public_base_url": public_base,
                "instagram_location_id": loc_id,
                "instagram_location_name": loc_name,
            }
        )
    else:
        _set_env("INSTAGRAM__ACCESS_TOKEN", token)
        _set_env("INSTAGRAM__ACCOUNT_ID", account)
        _set_env("APP__PUBLIC_BASE_URL", public_base)
        _set_env("INSTAGRAM__LOCATION_ID", loc_id)
        _set_env("INSTAGRAM__LOCATION_NAME", loc_name)
    return {
        "status": "success",
        "instagram_connected": True,
        "instagram_access_token_masked": _mask_secret(token),
        "location_id": loc_id or None,
        "location_name": loc_name or None,
    }


class UpdateAISettingsRequest(BaseModel):
    provider: str = "openrouter"
    api_key: str = ""
    model_name: Optional[str] = None


@app.get("/api/settings/ai")
def get_ai_settings():
    from initials_agent.runtime import _ai_api_key

    settings = get_settings()
    key = _ai_api_key()
    uid = current_user_id()
    if uid and uid != "local":
        img_key = cred_get("image_api_key")
        return {
            "ai_provider": cred_get("ai_provider") or "openrouter",
            "ai_model": cred_get("ai_model_name") or settings.ai.model_name,
            "ai_ready": bool(key),
            "ai_key_masked": _mask_secret(key),
            "image_provider": cred_get("image_provider") or "puter",
            "image_model": cred_get("image_model_name") or settings.image.model_name or "",
            "image_ready": bool(img_key),
            "image_key_masked": _mask_secret(img_key),
        }
    img_key = ""
    if settings.image.api_key:
        img_key = (settings.image.api_key.get_secret_value() or "").strip()
    return {
        "ai_provider": settings.ai.provider or "openrouter",
        "ai_model": settings.ai.model_name,
        "ai_ready": bool(key),
        "ai_key_masked": _mask_secret(key),
        "image_provider": settings.image.provider or "puter",
        "image_model": settings.image.model_name or "",
        "image_ready": bool(img_key),
        "image_key_masked": _mask_secret(img_key),
    }


@app.post("/api/settings/ai")
def update_ai_settings(req: UpdateAISettingsRequest):
    from initials_agent.runtime import _ai_api_key

    provider = (req.provider or "openrouter").lower().strip()
    if provider not in {"openrouter", "openai"}:
        raise HTTPException(status_code=400, detail="provider must be openrouter or openai")
    key = (req.api_key or "").strip()
    existing = _ai_api_key()
    if not key:
        key = existing
    if not key:
        raise HTTPException(status_code=400, detail="AI API key is required")
    model = (req.model_name or "").strip() or "deepseek/deepseek-v4-flash-0731"
    uid = current_user_id()
    if uid and uid != "local":
        save_credentials(
            {"ai_provider": provider, "ai_api_key": key, "ai_model_name": model}
        )
    else:
        from initials_agent.tenant import save_credentials as _save_local

        _save_local(
            {"ai_provider": provider, "ai_api_key": key, "ai_model_name": model},
            user_id="local",
        )
        _set_env("AI__PROVIDER", provider)
        _set_env("AI__API_KEY", key)
        _set_env("AI__MODEL_NAME", model)
    return {
        "status": "success",
        "ai_ready": True,
        "ai_provider": provider,
        "ai_model": model,
        "ai_key_masked": _mask_secret(key),
    }


@app.get("/api/stats")
def get_stats(session = Depends(get_session)):
    from initials_agent.db.models import PublishedPostModel, PipelineRunModel
    
    total_runs = session.query(PipelineRunModel).count()
    linkedin = session.query(PublishedPostModel).filter_by(platform="linkedin").count()
    instagram = session.query(PublishedPostModel).filter_by(platform="instagram").count()
    
    # Calculate a simple trend for demonstration based on db presence
    # In a real heavy analytics system, this would group by date
    
    from initials_agent.product.profile import load_profile
    profile = load_profile()
    return {
        "totalRuns": total_runs,
        "linkedinPosts": linkedin,
        "instagramPosts": instagram,
        "nextRun": f"{profile.schedule_time} {profile.timezone}"
        + (" · on" if profile.schedule_enabled else " · off"),
    }

@app.get("/api/pipeline/runs")
def get_recent_runs(session = Depends(get_session)):
    runs = session.query(PipelineRunModel).order_by(PipelineRunModel.created_at.desc()).limit(8).all()
    # Lightweight topic lookup — only when progress JSON lacks topic_title
    need_draft_match = any(
        r.status == "success"
        and not ((get_live_progress(r.id) or decode_progress(r.logs) or {}).get("topic_title"))
        for r in runs
    )
    drafts = []
    if need_draft_match:
        drafts = (
            session.query(ContentDraftModel)
            .order_by(ContentDraftModel.created_at.desc())
            .limit(15)
            .all()
        )
    res = []
    for r in runs:
        topic = "—"
        progress = get_live_progress(r.id) or decode_progress(r.logs)
        if progress and progress.get("topic_title"):
            topic = str(progress["topic_title"])
        elif r.status == "success" and drafts:
            # Match draft created near this run (not always "latest draft")
            run_ts = r.created_at
            best = None
            best_delta = None
            for d in drafts:
                if not d.created_at or not run_ts:
                    continue
                try:
                    delta = abs((d.created_at - run_ts).total_seconds())
                except TypeError:
                    # naive vs aware
                    a = d.created_at.replace(tzinfo=None) if getattr(d.created_at, "tzinfo", None) else d.created_at
                    b = run_ts.replace(tzinfo=None) if getattr(run_ts, "tzinfo", None) else run_ts
                    delta = abs((a - b).total_seconds())
                # Draft is saved near end of run — allow up to 15 min
                if delta <= 900 and (best_delta is None or delta < best_delta):
                    best = d
                    best_delta = delta
            if best:
                topic = best.topic.title if best.topic else best.title
            elif drafts:
                topic = drafts[0].topic.title if drafts[0].topic else drafts[0].title
        elif r.status == "running" and progress and progress.get("niche"):
            topic = f"Running… ({progress.get('niche')})"

        logs = (r.logs or "").strip()
        # Friendly status for UI — don't scare users with "Failed" for restarts
        if r.status == "success":
            ui_status = "Completed"
            # Note missing image when visual was skipped
            if progress:
                for st in progress.get("stages") or []:
                    if st.get("id") == "visual" and st.get("status") == "skipped":
                        ui_status = "Completed (no image)"
                        break
        elif r.status == "running":
            ui_status = "Running"
        elif r.status == "cancelled" or "interrupted:" in logs.lower() or "stale running" in logs.lower():
            ui_status = "Interrupted"
        elif r.status == "failed":
            ui_status = "Failed"
        else:
            ui_status = (r.status or "unknown").capitalize()
        res.append({
            "id": str(r.id),
            "date": r.run_date,
            "topic": topic,
            "status": ui_status,
            "raw_status": r.status,
            "platforms": "LinkedIn + Instagram",
            "logs": "" if logs.startswith("PROGRESS_JSON:") else logs,
            "log_summary": ("" if logs.startswith("PROGRESS_JSON:") else logs)[-240:] if logs else "",
        })
    return res

@app.get("/api/pipeline/status")
def get_pipeline_status(run_id: Optional[str] = None, session = Depends(get_session)):
    # Prefer the caller's run_id — UUID order is NOT chronological
    run = None
    if run_id:
        try:
            run = session.query(PipelineRunModel).filter_by(id=uuid.UUID(run_id)).first()
        except ValueError:
            run = None
    if not run:
        run = (
            session.query(PipelineRunModel)
            .filter(PipelineRunModel.status == "running")
            .order_by(PipelineRunModel.created_at.desc())
            .first()
        )
    if not run:
        run = session.query(PipelineRunModel).order_by(PipelineRunModel.created_at.desc()).first()
    if not run:
        return {
            "status": "idle",
            "stages": [],
            "run_id": None,
            "logs": "",
            "error": None,
            "percent": 0,
            "elapsed_s": 0,
            "eta_s": None,
            "elapsed_label": "0s",
            "eta_label": "--",
            "current_stage": None,
        }

    status = run.status
    payload_id = str(run.id)
    logs = (run.logs or "").strip()
    progress = get_live_progress(run.id) or decode_progress(logs)
    ui_status = {
        "success": "completed",
        "failed": "failed",
        "cancelled": "cancelled",
        "running": "running",
    }.get(status or "", status or "idle")

    if status == "success":
        enriched = enrich_progress(progress, run_status="completed")
    else:
        enriched = enrich_progress(progress, run_status=ui_status)

    error = None
    if status == "failed":
        error = (progress or {}).get("error") or (None if logs.startswith("PROGRESS_JSON:") else logs)
    elif status == "cancelled":
        error = (None if logs.startswith("PROGRESS_JSON:") else logs) or "Run was cancelled."

    return {
        "run_id": payload_id,
        "logs": logs if not logs.startswith("PROGRESS_JSON:") else "",
        "run_date": run.run_date,
        "status": ui_status if status != "success" else "completed",
        "error": error,
        "percent": enriched["percent"],
        "elapsed_s": enriched["elapsed_s"],
        "eta_s": enriched["eta_s"],
        "elapsed_label": enriched["elapsed_label"],
        "eta_label": enriched["eta_label"],
        "total_expected_s": enriched.get("total_expected_s"),
        "current_stage": enriched.get("current_stage"),
        "scale": enriched.get("scale"),
        "stages": enriched.get("stages") or [],
    }

@app.post("/api/pipeline/run")
async def trigger_pipeline(req: RunPipelineRequest, background_tasks: BackgroundTasks, session = Depends(get_session)):
    try:
        from initials_agent.runtime import _ai_api_key

        if not _ai_api_key():
            raise HTTPException(
                status_code=400,
                detail=(
                    "AI API key required. Add your key in Settings for this account. "
                    "Hardcoded drafts are disabled."
                ),
            )
        profile = load_profile()
        tenant_uid = current_user_id() or "local"
        tenant_email = current_user_email()
        # Re-clicks should join the in-flight run — cancelling mid-image left users with "nothing happened"
        existing = (
            session.query(PipelineRunModel)
            .filter_by(status="running")
            .order_by(PipelineRunModel.created_at.desc())
            .first()
        )
        if existing and not req.force:
            return {
                "status": "already_running",
                "run_id": str(existing.id),
                "niche_id": profile.active_niche_id,
                "niche_label": profile.niche_label(),
            }

        opts = RunOptions(
            dry_run=req.dry_run,
            force=req.force,
            topic=profile.research_query(),
            niche_id=profile.active_niche_id,
            no_image=req.no_image,
            no_publish=req.no_publish,
        )
        # Include microseconds so unique run_date never collides on rapid clicks
        run_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        progress = init_progress(
            niche=profile.niche_label(),
            no_image=req.no_image,
            no_publish=req.no_publish,
        )
        run_record = PipelineRunModel(
            run_date=run_date,
            status="running",
            retry_count=0,
            logs=encode_progress(progress),
        )
        session.add(run_record)
        session.commit()
        run_id = run_record.id
        from initials_agent.pipeline_progress import write_progress as _seed_progress

        _seed_progress(session, run_id, progress)
        opts.pipeline_run_id = run_id
        session.expire_all()
    except HTTPException:
        session.rollback()
        raise
    except Exception as e:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Could not start pipeline: {e}") from e

    async def task_runner(run_id, opts, tenant_uid, tenant_email):
        set_tenant(tenant_uid, tenant_email)
        try:
            db_engine = get_engine(tenant_db_url(tenant_uid))
            db_Session = get_session_factory(db_engine)
            task_session = db_Session()
            try:
                # Bail if this run was cancelled before the worker started
                record = task_session.query(PipelineRunModel).filter_by(id=run_id).first()
                if not record or record.status == "cancelled":
                    return
                task_agent = build_agent(task_session)
                try:
                    await task_agent.run(opts)
                    record = task_session.query(PipelineRunModel).filter_by(id=run_id).first()
                    if record and record.status == "running":
                        record.status = "success"
                        from initials_agent.pipeline_progress import (
                            clear_live_progress,
                            decode_progress,
                            encode_progress,
                            get_live_progress,
                        )

                        prog = get_live_progress(run_id) or decode_progress(record.logs)
                        if prog:
                            record.logs = encode_progress(prog)
                        clear_live_progress(run_id)
                        task_session.commit()
                except Exception as e:
                    task_session.rollback()
                    record = task_session.query(PipelineRunModel).filter_by(id=run_id).first()
                    if record and record.status == "running":
                        record.status = "failed"
                        from initials_agent.pipeline_progress import (
                            clear_live_progress,
                            decode_progress,
                            encode_progress,
                            get_live_progress,
                            mark_failed,
                        )

                        prog = get_live_progress(run_id) or decode_progress(record.logs) or {}
                        if prog:
                            mark_failed(prog, str(e))
                            record.logs = encode_progress(prog)
                        else:
                            record.logs = str(e)
                        clear_live_progress(run_id)
                        task_session.commit()
            finally:
                task_session.close()
        finally:
            clear_tenant()

    background_tasks.add_task(task_runner, run_id, opts, tenant_uid, tenant_email)
    return {
        "status": "started",
        "run_id": str(run_id),
        "niche_id": profile.active_niche_id,
        "niche_label": profile.niche_label(),
    }

@app.get("/api/content/latest")
def get_latest_content(session = Depends(get_session)):
    drafts = session.query(ContentDraftModel).order_by(ContentDraftModel.created_at.desc()).limit(8).all()
    if not drafts:
        return []
    draft_ids = [d.id for d in drafts]
    all_assets = (
        session.query(GeneratedAssetModel)
        .filter(GeneratedAssetModel.draft_id.in_(draft_ids))
        .all()
    )
    assets_by_draft: dict = {}
    for a in all_assets:
        assets_by_draft.setdefault(a.draft_id, []).append(a)

    res = []
    from initials_agent.services.approval.local import (
        caption_with_hashtags,
        instagram_image_paths_from_assets,
    )

    for d in drafts:
        assets = assets_by_draft.get(d.id, [])
        hashtags = d.hashtags or []
        ig = caption_with_hashtags(d.instagram_caption or "", hashtags)
        paths = instagram_image_paths_from_assets(assets)
        image_urls = []
        for p in paths:
            raw = str(p or "").strip()
            if not raw:
                continue
            if raw.startswith("http://") or raw.startswith("https://"):
                image_urls.append(raw)
            else:
                name = os.path.basename(raw.replace("\\", "/"))
                if name:
                    image_urls.append(f"/images/{name}")
        image_url = image_urls[0] if image_urls else None
        res.append({
            "id": str(d.id),
            "title": d.title,
            "hook": d.hook,
            "text": d.hook,
            "linkedin_post": d.linkedin_post,
            "instagram_caption": ig,
            "cta": d.cta,
            "hashtags": hashtags,
            "sources": d.source_references or [],
            "date": d.created_at.strftime("%b %d, %Y %H:%M"),
            "status": d.state,
            "image_url": image_url,
            "image_urls": image_urls,
            "carousel_count": len(image_urls),
            "category": (d.topic.description or "").split("]")[0].lstrip("[") if d.topic and d.topic.description and d.topic.description.startswith("[") else None,
        })
    return res


@app.get("/api/topics")
def get_topics(session=Depends(get_session), limit: int = 40):
    """Recent research topics (same list the desktop GUI used)."""
    limit = max(1, min(100, int(limit or 40)))
    profile = load_profile()
    rows = (
        session.query(TopicModel)
        .order_by(TopicModel.created_at.desc())
        .limit(limit)
        .all()
    )
    items = []
    for t in rows:
        draft = (
            session.query(ContentDraftModel)
            .filter_by(topic_id=t.id)
            .order_by(ContentDraftModel.created_at.desc())
            .first()
        )
        items.append(
            {
                "id": str(t.id),
                "title": t.title,
                "description": t.description,
                "angle": t.angle,
                "score": t.score,
                "date": t.created_at.strftime("%Y-%m-%d %H:%M") if t.created_at else "",
                "draft_id": str(draft.id) if draft else None,
                "draft_title": draft.title if draft else None,
                "draft_state": draft.state if draft else None,
            }
        )
    return {
        "active_niche_id": profile.active_niche_id,
        "niche_label": profile.niche_label(),
        "research_query": profile.research_query(),
        "topics": items,
    }


class UpdateSchedulerRequest(BaseModel):
    schedule_enabled: Optional[bool] = None
    schedule_time: Optional[str] = None
    timezone: Optional[str] = None
    publish_mode: Optional[str] = None
    active_niche_id: Optional[str] = None
    custom_niche_text: Optional[str] = None
    enabled_niche_ids: Optional[list[str]] = None


@app.get("/api/scheduler")
def get_scheduler(session=Depends(get_session)):
    """Schedule config + niche topic selection + recent runs."""
    profile = load_profile()
    runs = (
        session.query(PipelineRunModel)
        .order_by(PipelineRunModel.created_at.desc())
        .limit(12)
        .all()
    )
    recent = []
    for r in runs:
        logs = (r.logs or "").strip()
        if r.status == "success":
            ui = "Completed"
        elif r.status == "running":
            ui = "Running"
        elif r.status == "cancelled":
            ui = "Interrupted"
        elif r.status == "failed":
            ui = "Failed"
        else:
            ui = (r.status or "unknown").capitalize()
        recent.append(
            {
                "id": str(r.id),
                "date": r.run_date,
                "status": ui,
                "raw_status": r.status,
                "retries": r.retry_count,
            }
        )
    return {
        "schedule_enabled": profile.schedule_enabled,
        "schedule_time": profile.schedule_time,
        "timezone": profile.timezone,
        "publish_mode": profile.publish_mode,
        "active_niche_id": profile.active_niche_id,
        "custom_niche_text": profile.custom_niche_text,
        "enabled_niche_ids": list(profile.enabled_niche_ids or []),
        "niche_label": profile.niche_label(),
        "research_query": profile.research_query(),
        "niches": [{"id": n.id, "label": n.label} for n in NICHES],
        "next_run": (
            f"{profile.schedule_time} {profile.timezone}"
            + (" · on" if profile.schedule_enabled else " · off")
        ),
        "recent_runs": recent,
    }


@app.put("/api/scheduler")
def put_scheduler(req: UpdateSchedulerRequest):
    profile = load_profile()
    data = profile.model_dump()
    for key, value in req.model_dump(exclude_unset=True).items():
        if value is not None:
            data[key] = value
    if data.get("publish_mode") not in {
        "review",
        "auto_linkedin",
        "auto_instagram",
        "auto_both",
        None,
    }:
        raise HTTPException(status_code=400, detail="Invalid publish_mode")
    updated = BrandProfile.model_validate(data)
    # Keep active niche inside enabled set when possible
    enabled = list(updated.enabled_niche_ids or [])
    if enabled and updated.active_niche_id not in enabled:
        enabled.append(updated.active_niche_id)
        updated.enabled_niche_ids = enabled
    save_profile(updated)
    return {
        "status": "success",
        "schedule_enabled": updated.schedule_enabled,
        "schedule_time": updated.schedule_time,
        "timezone": updated.timezone,
        "publish_mode": updated.publish_mode,
        "active_niche_id": updated.active_niche_id,
        "niche_label": updated.niche_label(),
        "enabled_niche_ids": updated.enabled_niche_ids,
        "research_query": updated.research_query(),
        "next_run": (
            f"{updated.schedule_time} {updated.timezone}"
            + (" · on" if updated.schedule_enabled else " · off")
        ),
    }


@app.post("/api/scheduler/run-now")
async def scheduler_run_now(background_tasks: BackgroundTasks, session=Depends(get_session)):
    """Force a generate using the active niche from Scheduler settings."""
    profile = load_profile()
    no_publish = profile.publish_mode == "review"
    req = RunPipelineRequest(dry_run=False, force=False, no_image=False, no_publish=no_publish)
    return await trigger_pipeline(req, background_tasks, session)


class GenerateVisualRequest(BaseModel):
    topic: str
    prompt: str
    platform: str
    aspect_ratio: str

class UpdateImageProviderRequest(BaseModel):
    provider: str
    api_key: str = ""
    model_name: Optional[str] = None

@app.post("/api/settings/image")
def update_image_settings(req: UpdateImageProviderRequest):
    settings = get_settings()
    provider = (req.provider or "puter").strip().lower() or "puter"
    # Legacy providers removed — Settings is Puter-first
    if provider in {"bfl", "cloudflare", "pollinations", "nvidia", "flux"}:
        provider = "puter"
    allowed = {"puter", "openrouter", "dalle", "gemini", "mock"}
    if provider not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Image provider must be one of: {', '.join(sorted(allowed))}",
        )
    key = (req.api_key or "").strip()
    uid = current_user_id()
    if not key:
        if uid and uid != "local":
            key = cred_get("image_api_key")
        elif settings.image.api_key:
            key = (settings.image.api_key.get_secret_value() or "").strip()
    if not key and provider != "mock":
        raise HTTPException(status_code=400, detail="Image API key / Puter token is required")
    model = (req.model_name or "").strip()
    if not model:
        model = "openai/gpt-image-2" if provider == "puter" else (settings.image.model_name or "")
    if uid and uid != "local":
        payload = {"image_provider": provider, "image_api_key": key}
        if model:
            payload["image_model_name"] = model
        save_credentials(payload)
    else:
        # Also persist to local credentials so Settings survives process restart
        if uid == "local" or not uid:
            from initials_agent.tenant import save_credentials as _save_local

            payload = {"image_provider": provider, "image_api_key": key}
            if model:
                payload["image_model_name"] = model
            _save_local(payload, user_id="local")
        _set_env("IMAGE__PROVIDER", provider)
        if key:
            _set_env("IMAGE__API_KEY", key)
        if model:
            _set_env("IMAGE__MODEL_NAME", model)
    return {
        "status": "success",
        "image_provider": provider,
        "image_ready": bool(key) or provider == "mock",
        "image_key_masked": _mask_secret(key),
        "image_model": model,
    }

# In-memory job state store for visual generation (In production, use Redis or DB with background worker)
VISUAL_JOBS: Dict[str, Any] = {}

def process_visual_generation(job_id: str, req_data: dict):
    db_engine = get_engine(tenant_db_url())
    db_Session = get_session_factory(db_engine)
    with db_Session() as task_session:
        from initials_agent.db.models import StandaloneVisualModel
        settings = get_settings()
        
        VISUAL_JOBS[job_id]["status"] = "Preparing prompt"
        
        # Build the proper provider
        provider_name = settings.image.provider
        if provider_name == "dalle" and settings.image.api_key:
            from initials_agent.providers.image.dalle import DalleImageProvider
            provider = DalleImageProvider(settings.image.api_key.get_secret_value())
        elif provider_name == "gemini" and settings.image.api_key:
            from initials_agent.providers.image.gemini import GeminiImageProvider
            provider = GeminiImageProvider(
                settings.image.api_key.get_secret_value(),
                settings.image.model_name,
            )
        elif provider_name == "openrouter" and settings.image.api_key:
            from initials_agent.providers.image.openrouter import OpenRouterImageProvider
            provider = OpenRouterImageProvider(
                settings.image.api_key.get_secret_value(),
                settings.image.model_name,
            )
        elif provider_name == "puter" and settings.image.api_key:
            from initials_agent.providers.image.puter import PuterImageProvider
            provider = PuterImageProvider(
                settings.image.api_key.get_secret_value(),
                settings.image.model_name,
            )
        else:
            provider = None # Will error out

        if provider is not None:
            def _on_retry(attempt: int, wait: int) -> None:
                VISUAL_JOBS[job_id]["status"] = f"Rate limited, waiting {wait}s (retry {attempt})"

            provider.on_retry = _on_retry
            
        if not provider:
            VISUAL_JOBS[job_id]["status"] = "Failed"
            VISUAL_JOBS[job_id]["error"] = "Image generation is not configured."
            # Save failed record
            vis = StandaloneVisualModel(
                topic=req_data["topic"], prompt=req_data["prompt"], provider=provider_name,
                status="failed", generation_error="Image generation is not configured."
            )
            task_session.add(vis)
            task_session.commit()
            return

        VISUAL_JOBS[job_id]["status"] = "Calling image provider"
        try:
            from initials_agent.models.content import VisualConcept
            import asyncio
            concept = VisualConcept(
                aspect_ratio=req_data.get("aspect_ratio", "1:1"),
                composition="minimal",
                headline="CLI Prompt",
                supporting_text="",
                visual_subject=req_data["prompt"],
                environment="studio",
                lighting="cinematic",
                color_palette="dark",
                typography="none",
                negative_prompt="",
                brand_requirements=""
            )
            
            # The agent.ImageGenerationService expects a provider.
            # We can use the provider directly.
            image_bytes = asyncio.run(provider.generate_image(concept))
            
            VISUAL_JOBS[job_id]["status"] = "Saving image"
            # Ensure it's in the output/images directory
            os.makedirs(os.path.join(os.getcwd(), "output", "images"), exist_ok=True)
            filename = f"gen_{uuid.uuid4().hex[:8]}.png"
            dest = os.path.join(os.getcwd(), "output", "images", filename)
            
            with open(dest, "wb") as f:
                f.write(image_bytes)
            
            # Save successful record
            vis = StandaloneVisualModel(
                topic=req_data["topic"], prompt=req_data["prompt"], provider=provider_name,
                image_url=f"/images/{filename}", width=1080, height=1350, status="success"
            )
            task_session.add(vis)
            task_session.commit()
            
            VISUAL_JOBS[job_id]["status"] = "Completed"
            VISUAL_JOBS[job_id]["result"] = {
                "id": str(vis.id),
                "image_url": vis.image_url,
                "created_at": vis.created_at.strftime("%b %d, %Y %H:%M"),
                "provider": provider_name.capitalize(),
                "dimensions": "1080 × 1350"
            }
        except Exception as e:
            VISUAL_JOBS[job_id]["status"] = "Failed"
            VISUAL_JOBS[job_id]["error"] = str(e)
            vis = StandaloneVisualModel(
                topic=req_data["topic"], prompt=req_data["prompt"], provider=provider_name,
                status="failed", generation_error=str(e)
            )
            task_session.add(vis)
            task_session.commit()

@app.post("/api/visuals/generate")
async def start_visual_generation(req: GenerateVisualRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    VISUAL_JOBS[job_id] = {"status": "Starting", "result": None, "error": None}
    background_tasks.add_task(process_visual_generation, job_id, req.model_dump())
    return {"job_id": job_id}

@app.get("/api/visuals/jobs/{job_id}")
def get_visual_job(job_id: str):
    if job_id not in VISUAL_JOBS:
        raise HTTPException(status_code=404, detail="Job not found")
    return VISUAL_JOBS[job_id]

class UseVisualRequest(BaseModel):
    image_id: str
    content_id: str

@app.post("/api/visuals/use")
def use_visual(req: UseVisualRequest, session=Depends(get_session)):
    from initials_agent.db.models import StandaloneVisualModel, GeneratedAssetModel
    vis = session.query(StandaloneVisualModel).filter_by(id=req.image_id).first()
    if not vis:
        raise HTTPException(status_code=404, detail="Visual not found")
    
    asset = GeneratedAssetModel(
        draft_id=req.content_id,
        url=vis.image_url,
        asset_type="image"
    )
    session.add(asset)
    
    vis.content_id = req.content_id
    session.commit()
    return {"status": "success"}

@app.get("/api/content/queue")
def get_approval_queue(session = Depends(get_session)):
    reqs = session.query(ApprovalRequestModel).filter_by(status="pending").all()
    out = []
    from initials_agent.services.approval.local import (
        caption_with_hashtags,
        instagram_image_paths_from_assets,
    )

    for r in reqs:
        draft = r.draft
        paths = instagram_image_paths_from_assets(draft.assets if draft else [])
        out.append({
            "id": str(r.id),
            "draft_id": str(r.draft_id),
            "linkedin_content": draft.linkedin_post if draft else "",
            "instagram_content": caption_with_hashtags(
                draft.instagram_caption if draft else "",
                getattr(draft, "hashtags", None) if draft else None,
            ),
            "quality_score": None,
            "image_path": paths[0] if paths else None,
            "image_paths": paths,
        })
    return out

@app.post("/api/content/{id}/approve")
async def approve_content(id: str, session=Depends(get_session)):
    """Approve by approval-request id OR draft id, then publish to connected networks."""
    service = LocalApprovalService(ApprovalRepository(session))
    req_uuid = uuid.UUID(id)
    model = session.query(ApprovalRequestModel).filter_by(id=req_uuid).first()
    if not model:
        model = session.query(ApprovalRequestModel).filter_by(draft_id=req_uuid).first()
    if not model:
        raise HTTPException(status_code=404, detail="Approval request not found")
    service.approve(model.id)
    session.commit()

    publish_result = None
    try:
        from initials_agent.product.profile import load_profile, platforms_for_mode

        profile = load_profile()
        platforms = platforms_for_mode(profile.publish_mode) or ["linkedin", "instagram"]
        agent = build_agent(session)
        session.refresh(model)
        domain = agent.approval._map_to_domain(model)
        from initials_agent.models.workflow import ApprovalStatus

        domain.status = ApprovalStatus.APPROVED
        publish_result = await agent.publishing.publish_approved_request(domain, platforms=platforms)
    except Exception as e:
        publish_result = {"error": str(e)}

    return {"status": "approved", "publish": publish_result}

@app.post("/api/content/{id}/reject")
def reject_content(id: str, session = Depends(get_session)):
    service = LocalApprovalService(ApprovalRepository(session))
    service.reject(uuid.UUID(id))
    session.commit()
    return {"status": "rejected"}


@app.delete("/api/content/{id}")
def delete_content(id: str, session=Depends(get_session)):
    """Delete a draft and all related rows (assets, QC, approvals, publishes)."""
    try:
        draft_id = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid draft id")

    draft = session.query(ContentDraftModel).filter_by(id=draft_id).first()
    if not draft:
        raise HTTPException(status_code=404, detail="Draft not found")

    published = session.query(PublishedPostModel).filter_by(draft_id=draft_id).all()
    for post in published:
        session.query(AnalyticsModel).filter_by(post_id=post.id).delete(synchronize_session=False)
        session.delete(post)

    session.query(ApprovalRequestModel).filter_by(draft_id=draft_id).delete(synchronize_session=False)
    session.query(QualityCheckModel).filter_by(draft_id=draft_id).delete(synchronize_session=False)
    session.query(GeneratedAssetModel).filter_by(draft_id=draft_id).delete(synchronize_session=False)
    session.query(VisualConceptModel).filter_by(draft_id=draft_id).delete(synchronize_session=False)
    session.query(StandaloneVisualModel).filter_by(content_id=draft_id).update(
        {StandaloneVisualModel.content_id: None}, synchronize_session=False
    )
    session.delete(draft)
    session.commit()
    return {"status": "deleted", "id": str(draft_id)}


# ---------------------------------------------------------------------------
# SaaS (Supabase Auth + jobs + cron)
# ---------------------------------------------------------------------------
from fastapi import Header

from initials_agent.saas import (
    admin_accounts,
    admin_brand_detail,
    admin_failures,
    admin_overview,
    clear_platform_storage,
    create_job,
    cron_secret_ok,
    get_brands_for_user,
    list_brands_due_for_schedule,
    require_admin,
    supabase_configured,
    supabase_rest,
    upsert_user_brand,
    verify_supabase_jwt,
)


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Expected Bearer token")
    return parts[1].strip()


@app.get("/api/saas/status")
def saas_status():
    settings = get_settings()
    return {
        "supabase_configured": supabase_configured(),
        "saas_enabled": bool(settings.saas.enabled),
        "cron_configured": bool(settings.saas.cron_secret),
        "storage_bucket": settings.supabase.storage_bucket,
        "api_build": API_BUILD,
    }


@app.get("/api/saas/me")
async def saas_me(authorization: str | None = Header(default=None)):
    if not supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured on the server")
    token = _bearer_token(authorization)
    try:
        user = await verify_supabase_jwt(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    brands = await get_brands_for_user(user.id)
    return {
        "user": {"id": user.id, "email": user.email},
        "brands": brands,
    }


class OnboardRequest(BaseModel):
    business_name: str
    positioning: str = ""
    audience: str = ""
    offer: str = ""
    cta_text: str = "Book a demo"
    website_url: str = ""
    active_niche_id: str = "ai_automation"
    custom_niche_text: str = ""


@app.post("/api/saas/onboard")
async def saas_onboard(req: OnboardRequest, authorization: str | None = Header(default=None)):
    """Save brand profile collected at registration (Supabase brand + local profile)."""
    if not supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured on the server")
    token = _bearer_token(authorization)
    try:
        user = await verify_supabase_jwt(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    name = (req.business_name or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Business name is required")
    positioning = (req.positioning or "").strip()
    if not positioning:
        raise HTTPException(status_code=400, detail="Positioning is required")

    fields = {
        "business_name": name,
        "positioning": positioning,
        "audience": (req.audience or "").strip(),
        "offer": (req.offer or "").strip(),
        "cta_text": (req.cta_text or "Book a demo").strip() or "Book a demo",
        "website_url": (req.website_url or "").strip(),
        "active_niche_id": (req.active_niche_id or "ai_automation").strip(),
        "custom_niche_text": (req.custom_niche_text or "").strip(),
        "setup_complete": True,
    }
    try:
        brand = await upsert_user_brand(user.id, fields)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Mirror into local desktop profile used by the generate pipeline
    profile = load_profile()
    data = profile.model_dump()
    data.update(fields)
    updated = BrandProfile.model_validate(data)
    save_profile(updated)

    return {"status": "ok", "brand": brand, "niche_label": updated.niche_label()}


class CreateGenerateJobRequest(BaseModel):
    brand_id: str
    no_image: bool = False


@app.post("/api/saas/jobs/generate")
async def saas_enqueue_generate(
    req: CreateGenerateJobRequest,
    authorization: str | None = Header(default=None),
):
    """Queue a generate job for a brand the user owns. Worker execution comes next."""
    if not supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured on the server")
    token = _bearer_token(authorization)
    try:
        user = await verify_supabase_jwt(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    brands = await get_brands_for_user(user.id)
    if not any(str(b.get("id")) == req.brand_id for b in brands):
        raise HTTPException(status_code=403, detail="Brand not found for this user")

    job = await create_job(
        req.brand_id,
        "generate",
        {"no_image": req.no_image, "requested_by": user.id},
    )
    return {"status": "queued", "job": job}


@app.get("/api/saas/jobs/{job_id}")
async def saas_get_job(job_id: str, authorization: str | None = Header(default=None)):
    if not supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    token = _bearer_token(authorization)
    try:
        user = await verify_supabase_jwt(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    rows = await supabase_rest(
        "GET",
        "jobs",
        params={"id": f"eq.{job_id}", "select": "*"},
    )
    if not rows:
        raise HTTPException(status_code=404, detail="Job not found")
    job = rows[0] if isinstance(rows, list) else rows
    brands = await get_brands_for_user(user.id)
    if not any(str(b.get("id")) == str(job.get("brand_id")) for b in brands):
        raise HTTPException(status_code=403, detail="Forbidden")
    return job


@app.get("/api/saas/drafts")
async def saas_list_drafts(
    brand_id: str,
    authorization: str | None = Header(default=None),
):
    if not supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    token = _bearer_token(authorization)
    try:
        user = await verify_supabase_jwt(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    brands = await get_brands_for_user(user.id)
    if not any(str(b.get("id")) == brand_id for b in brands):
        raise HTTPException(status_code=403, detail="Brand not found for this user")

    drafts = await supabase_rest(
        "GET",
        "content_drafts",
        params={
            "brand_id": f"eq.{brand_id}",
            "select": "*,generated_assets(url,asset_type,created_at)",
            "order": "created_at.desc",
            "limit": "20",
        },
    )
    return {"drafts": drafts or []}


@app.post("/api/internal/cron/daily")
async def saas_cron_daily(x_cron_secret: str | None = Header(default=None)):
    """Called by Render Cron / external cron. Enqueues generate jobs for scheduled brands."""
    if not cron_secret_ok(x_cron_secret):
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    if not supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")

    brands = await list_brands_due_for_schedule()
    queued = []
    for brand in brands:
        bid = str(brand.get("id"))
        job = await create_job(bid, "cron_daily", {"source": "cron"})
        queued.append({"brand_id": bid, "job_id": job.get("id"), "name": brand.get("business_name")})
    return {
        "status": "ok",
        "queued_count": len(queued),
        "jobs": queued,
        "note": "Jobs are queued; a worker must process them (next milestone).",
    }


@app.post("/api/saas/backfill-images")
async def saas_backfill_images(authorization: str | None = Header(default=None)):
    """Upload existing local images to Supabase Storage and sync draft rows."""
    if not supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    token = _bearer_token(authorization)
    try:
        await verify_supabase_jwt(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    from initials_agent.saas.sync import backfill_local_db_images_to_supabase

    result = await backfill_local_db_images_to_supabase(limit=50)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error") or "backfill failed")
    return result


class ResetStorageRequest(BaseModel):
    confirm: str = ""
    all_brands: bool = False


@app.post("/api/saas/reset-storage")
async def saas_reset_storage(
    req: ResetStorageRequest,
    authorization: str | None = Header(default=None),
):
    """Clear Supabase Storage + cloud rows + local pipeline runs / drafts (the '63' counter)."""
    if not supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    if (req.confirm or "").strip().upper() != "RESET":
        raise HTTPException(
            status_code=400,
            detail='Type confirm: "RESET" to clear platform storage',
        )
    token = _bearer_token(authorization)
    try:
        user = await verify_supabase_jwt(token)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    brands = await get_brands_for_user(user.id)
    if not brands:
        raise HTTPException(status_code=404, detail="No brand for this user")

    try:
        if req.all_brands:
            cloud = await clear_platform_storage(brand_id=None)
        else:
            totals = {
                "files_deleted": 0,
                "asset_rows_cleared": 0,
                "brands": [],
                "cloud_tables_cleared": {},
            }
            for b in brands:
                bid = str(b["id"])
                part = await clear_platform_storage(brand_id=bid)
                totals["files_deleted"] += int(part.get("files_deleted") or 0)
                totals["asset_rows_cleared"] += int(part.get("asset_rows_cleared") or 0)
                totals["brands"].append(bid)
                for k, v in (part.get("cloud_tables_cleared") or {}).items():
                    totals["cloud_tables_cleared"][k] = totals["cloud_tables_cleared"].get(k, 0) + (
                        v if isinstance(v, int) and v >= 0 else 0
                    )
            cloud = {"ok": True, **totals}

        from initials_agent.saas.local_reset import clear_local_platform_data

        local = clear_local_platform_data(clear_images_dir=True)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return {
        "ok": True,
        "cloud": cloud,
        "local": local,
        "note": "Local pipeline_runs cleared (this was the '63' Total Runs count).",
    }


# ---------------------------------------------------------------------------
# Platform admin (allowlisted emails via SAAS__ADMIN_EMAILS)
# ---------------------------------------------------------------------------


async def _require_admin_user(authorization: str | None):
    if not supabase_configured():
        raise HTTPException(status_code=503, detail="Supabase is not configured")
    token = _bearer_token(authorization)
    try:
        user = await verify_supabase_jwt(token)
        require_admin(user)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return user


@app.get("/api/admin/me")
async def admin_me(authorization: str | None = Header(default=None)):
    user = await _require_admin_user(authorization)
    return {"admin": True, "email": user.email, "user_id": user.id}


@app.get("/api/admin/overview")
async def admin_overview_route(authorization: str | None = Header(default=None)):
    await _require_admin_user(authorization)
    try:
        return await admin_overview()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/admin/accounts")
async def admin_accounts_route(authorization: str | None = Header(default=None)):
    await _require_admin_user(authorization)
    try:
        accounts = await admin_accounts()
        return {"accounts": accounts}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/api/admin/brands/{brand_id}")
async def admin_brand_route(brand_id: str, authorization: str | None = Header(default=None)):
    await _require_admin_user(authorization)
    try:
        detail = await admin_brand_detail(brand_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if not detail:
        raise HTTPException(status_code=404, detail="Brand not found")
    return detail


@app.get("/api/admin/failures")
async def admin_failures_route(
    authorization: str | None = Header(default=None),
    limit: int = 50,
):
    await _require_admin_user(authorization)
    lim = max(1, min(limit, 100))
    try:
        items = await admin_failures(limit=lim)
        return {"failures": items}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

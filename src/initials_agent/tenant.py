"""Per-user workspace isolation (profile, SQLite, API/social credentials)."""

from __future__ import annotations

import json
import os
from contextvars import ContextVar
from pathlib import Path
from typing import Any

_user_id: ContextVar[str | None] = ContextVar("tenant_user_id", default=None)
_user_email: ContextVar[str | None] = ContextVar("tenant_user_email", default=None)


def set_tenant(user_id: str, email: str | None = None) -> None:
    _user_id.set((user_id or "").strip() or None)
    _user_email.set((email or "").strip() or None)


def clear_tenant() -> None:
    _user_id.set(None)
    _user_email.set(None)


def current_user_id() -> str | None:
    return _user_id.get()


def current_user_email() -> str | None:
    return _user_email.get()


def app_home() -> Path:
    override = os.environ.get("DAILY_CONTENT_AGENT_HOME")
    if override:
        root = Path(override)
    elif os.name == "nt":
        root = Path(os.environ.get("APPDATA", Path.home())) / "DailyContentAgent"
    else:
        root = Path.home() / ".config" / "DailyContentAgent"
    root.mkdir(parents=True, exist_ok=True)
    return root


def workspace_dir(user_id: str | None = None) -> Path:
    """Isolated folder per auth user. CLI / no-auth uses `local`."""
    uid = (user_id or current_user_id() or "local").strip() or "local"
    # Keep path filesystem-safe
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in uid)
    path = app_home() / "users" / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def profile_path(user_id: str | None = None) -> Path:
    return workspace_dir(user_id) / "profile.json"


def credentials_path(user_id: str | None = None) -> Path:
    return workspace_dir(user_id) / "credentials.json"


def tenant_db_path(user_id: str | None = None) -> Path:
    return workspace_dir(user_id) / "data.db"


def tenant_db_url(user_id: str | None = None) -> str:
    path = tenant_db_path(user_id).resolve()
    return f"sqlite:///{path.as_posix()}"


def tenant_images_dir(user_id: str | None = None) -> Path:
    """Web-served path: /images/<user>/… under the API process cwd."""
    uid = (user_id or current_user_id() or "local").strip() or "local"
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in uid)
    path = Path.cwd() / "output" / "images" / safe
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_credentials(user_id: str | None = None) -> dict[str, Any]:
    path = credentials_path(user_id)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_credentials(updates: dict[str, Any], user_id: str | None = None) -> dict[str, Any]:
    """Merge updates into this user's credentials.json (blank values keep existing)."""
    current = load_credentials(user_id)
    for key, value in updates.items():
        if value is None:
            continue
        if isinstance(value, str) and not value.strip() and key.endswith(("key", "token", "secret")):
            # blank secret = keep previous
            continue
        current[key] = value.strip() if isinstance(value, str) else value
    path = credentials_path(user_id)
    path.write_text(json.dumps(current, indent=2), encoding="utf-8")
    meta = {"user_id": current_user_id(), "email": current_user_email()}
    meta_path = workspace_dir(user_id) / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return current


def cred_get(key: str, default: str = "", user_id: str | None = None) -> str:
    val = load_credentials(user_id).get(key, default)
    if val is None:
        return default
    return str(val).strip().strip("'").strip('"')


_db_ready: set[str] = set()


def ensure_tenant_db(user_id: str | None = None) -> None:
    from initials_agent.db.models import Base
    from initials_agent.db.session import get_engine

    uid = (user_id or current_user_id() or "local").strip() or "local"
    if uid in _db_ready:
        return
    engine = get_engine(tenant_db_url(uid))
    Base.metadata.create_all(engine)
    _db_ready.add(uid)

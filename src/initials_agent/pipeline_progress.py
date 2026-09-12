"""Pipeline run progress — in-memory live store + JSON on PipelineRunModel.logs."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime
from typing import Any

PROGRESS_PREFIX = "PROGRESS_JSON:"

_lock = threading.Lock()
_LIVE: dict[str, dict[str, Any]] = {}

# Typical wall times from local Puter + AI runs (seconds).
DEFAULT_STAGES: list[dict[str, Any]] = [
    {"id": "research", "name": "Research", "expected_s": 12},
    {"id": "topic", "name": "Topic Selection", "expected_s": 3},
    {"id": "writing", "name": "Writing", "expected_s": 35},
    {"id": "visual", "name": "Visual Generation", "expected_s": 75},
    {"id": "quality", "name": "Quality Control", "expected_s": 12},
    {"id": "save", "name": "Save & Sync", "expected_s": 8},
    {"id": "publish", "name": "Publishing", "expected_s": 15},
]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def stage_plan(*, no_image: bool = False, no_publish: bool = False) -> list[dict[str, Any]]:
    stages: list[dict[str, Any]] = []
    for s in DEFAULT_STAGES:
        if s["id"] == "visual" and no_image:
            continue
        if s["id"] == "publish" and no_publish:
            continue
        stages.append(
            {
                "id": s["id"],
                "name": s["name"],
                "expected_s": int(s["expected_s"]),
                "status": "pending",
                "started_at": None,
                "ended_at": None,
            }
        )
    return stages


def init_progress(
    *,
    niche: str = "",
    no_image: bool = False,
    no_publish: bool = False,
) -> dict[str, Any]:
    return {
        "v": 1,
        "started_at": _now_iso(),
        "niche": niche,
        "no_image": no_image,
        "no_publish": no_publish,
        "stages": stage_plan(no_image=no_image, no_publish=no_publish),
        "error": None,
    }


def encode_progress(progress: dict[str, Any]) -> str:
    return PROGRESS_PREFIX + json.dumps(progress, separators=(",", ":"))


def decode_progress(logs: str | None) -> dict[str, Any] | None:
    if not logs:
        return None
    text = logs.strip()
    if text.startswith(PROGRESS_PREFIX):
        raw = text[len(PROGRESS_PREFIX) :]
        if "\n" in raw:
            raw = raw.split("\n", 1)[0]
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def get_live_progress(run_id: uuid.UUID | str | None) -> dict[str, Any] | None:
    if not run_id:
        return None
    with _lock:
        data = _LIVE.get(str(run_id))
        return json.loads(json.dumps(data)) if data else None


def clear_live_progress(run_id: uuid.UUID | str | None) -> None:
    if not run_id:
        return
    with _lock:
        _LIVE.pop(str(run_id), None)


def advance_stage(progress: dict[str, Any], stage_id: str) -> dict[str, Any]:
    """Mark stage_id as running; complete any earlier running stages."""
    now = _now_iso()
    found = False
    for stage in progress.get("stages") or []:
        if stage.get("id") == stage_id:
            found = True
            if stage.get("status") == "pending":
                stage["status"] = "running"
                stage["started_at"] = now
            elif stage.get("status") != "completed":
                stage["status"] = "running"
                stage["started_at"] = stage.get("started_at") or now
            break
        if not found and stage.get("status") in ("pending", "running"):
            if stage.get("status") == "pending":
                stage["started_at"] = stage.get("started_at") or now
            stage["status"] = "completed"
            stage["ended_at"] = now
    return progress


def complete_stage(progress: dict[str, Any], stage_id: str) -> dict[str, Any]:
    now = _now_iso()
    for stage in progress.get("stages") or []:
        if stage.get("id") == stage_id:
            if stage.get("status") == "pending":
                stage["started_at"] = now
            stage["status"] = "completed"
            stage["ended_at"] = now
            break
    return progress


def skip_stage(progress: dict[str, Any], stage_id: str, reason: str = "skipped") -> dict[str, Any]:
    now = _now_iso()
    for stage in progress.get("stages") or []:
        if stage.get("id") == stage_id:
            stage["status"] = "skipped"
            stage["started_at"] = stage.get("started_at") or now
            stage["ended_at"] = now
            stage["note"] = reason
            break
    return progress


def mark_failed(progress: dict[str, Any], error: str) -> dict[str, Any]:
    now = _now_iso()
    progress["error"] = error
    for stage in progress.get("stages") or []:
        if stage.get("status") == "running":
            stage["status"] = "failed"
            stage["ended_at"] = now
    return progress


def complete_all(progress: dict[str, Any]) -> dict[str, Any]:
    now = _now_iso()
    for stage in progress.get("stages") or []:
        if stage.get("status") in ("pending", "running"):
            if stage.get("status") == "pending":
                stage["started_at"] = now
            stage["status"] = "completed"
            stage["ended_at"] = now
    return progress


def _stage_elapsed_s(stage: dict[str, Any], now: datetime) -> float | None:
    start = _parse_iso(stage.get("started_at"))
    if not start:
        return None
    end = _parse_iso(stage.get("ended_at")) or now
    return max(0.0, (end - start).total_seconds())


def format_duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "--"
    s = max(0, int(round(float(seconds))))
    if s < 60:
        return f"{s}s"
    m, rem = divmod(s, 60)
    if m < 60:
        return f"{m}m {rem}s"
    h, m = divmod(m, 60)
    return f"{h}h {m}m"


def enrich_progress(progress: dict[str, Any] | None, *, run_status: str) -> dict[str, Any]:
    """Build API-facing progress with elapsed, ETA, and percent."""
    now = datetime.now(UTC)
    if not progress:
        return {
            "percent": 0,
            "elapsed_s": 0,
            "eta_s": None,
            "elapsed_label": "0s",
            "eta_label": "--",
            "total_expected_s": sum(s["expected_s"] for s in DEFAULT_STAGES),
            "current_stage": None,
            "stages": [],
        }

    started = _parse_iso(progress.get("started_at")) or now
    elapsed_s = max(0.0, (now - started).total_seconds())
    stages_in = list(progress.get("stages") or [])

    ratios: list[float] = []
    for stage in stages_in:
        if stage.get("status") != "completed":
            continue
        expected = float(stage.get("expected_s") or 0)
        actual = _stage_elapsed_s(stage, now)
        if expected > 0 and actual is not None and actual >= 1:
            ratios.append(actual / expected)
    scale = 1.0
    if ratios:
        scale = sum(ratios) / len(ratios)
        scale = max(0.55, min(2.2, scale))

    enriched: list[dict[str, Any]] = []
    weight_done = 0.0
    weight_total = 0.0
    eta_remaining = 0.0
    current_name: str | None = None

    for stage in stages_in:
        expected = float(stage.get("expected_s") or 1)
        weight_total += expected
        status = (stage.get("status") or "pending").lower()
        elapsed = _stage_elapsed_s(stage, now)
        adj_expected = expected * scale

        if status == "completed":
            weight_done += expected
            time_label = format_duration(elapsed)
        elif status == "skipped":
            weight_done += expected
            time_label = "skipped"
        elif status == "failed":
            weight_done += expected * 0.5
            time_label = format_duration(elapsed)
        elif status == "running":
            current_name = stage.get("name")
            frac = 0.0
            if adj_expected > 0 and elapsed is not None:
                frac = min(0.92, elapsed / adj_expected)
            weight_done += expected * frac
            left = max(3.0, adj_expected - (elapsed or 0))
            eta_remaining += left
            time_label = f"{format_duration(elapsed)} | ~{format_duration(left)} left"
        else:
            eta_remaining += adj_expected
            time_label = f"~{format_duration(adj_expected)}"

        enriched.append(
            {
                "id": stage.get("id"),
                "name": stage.get("name"),
                "status": status,
                "expected_s": int(expected),
                "elapsed_s": int(round(elapsed)) if elapsed is not None else None,
                "time": time_label,
                "note": stage.get("note"),
            }
        )

    if run_status in ("success", "completed"):
        percent = 100
        eta_remaining = 0
        for s in enriched:
            if s["status"] in ("pending", "running"):
                s["status"] = "completed"
    elif run_status in ("failed", "cancelled"):
        percent = int(round(100 * weight_done / weight_total)) if weight_total else 0
        eta_remaining = 0
    else:
        percent = int(round(100 * weight_done / weight_total)) if weight_total else 0
        percent = max(1, min(99, percent)) if run_status == "running" else percent

    return {
        "percent": percent,
        "elapsed_s": int(round(elapsed_s)),
        "eta_s": int(round(eta_remaining)) if run_status == "running" else 0,
        "elapsed_label": format_duration(elapsed_s),
        "eta_label": format_duration(eta_remaining) if run_status == "running" else "0s",
        "total_expected_s": int(round(weight_total * scale)),
        "current_stage": current_name,
        "scale": round(scale, 2),
        "stages": enriched,
        "started_at": progress.get("started_at"),
        "niche": progress.get("niche"),
        "error": progress.get("error"),
    }


def write_progress(session, run_id: uuid.UUID | None, progress: dict[str, Any]) -> None:
    """Update live in-memory progress (and best-effort persist to run.logs)."""
    if not run_id:
        return
    key = str(run_id)
    with _lock:
        _LIVE[key] = json.loads(json.dumps(progress))

    # Persist without committing the agent session (avoids partial draft commits)
    try:
        from initials_agent.db.models import PipelineRunModel

        row = session.query(PipelineRunModel).filter_by(id=run_id).first()
        if row:
            row.logs = encode_progress(progress)
            session.flush()
    except Exception:
        pass

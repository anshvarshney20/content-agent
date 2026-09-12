"""Local SQLite cleanup for platform reset."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from initials_agent.db.models import (
    AnalyticsModel,
    ApprovalRequestModel,
    ContentDraftModel,
    GeneratedAssetModel,
    PipelineRunModel,
    PublishedPostModel,
    QualityCheckModel,
    ResearchSourceModel,
    StandaloneVisualModel,
    TopicModel,
    VisualConceptModel,
)
from initials_agent.db.session import get_engine, get_session_factory
from initials_agent.tenant import tenant_db_url, tenant_images_dir

logger = logging.getLogger(__name__)


def clear_local_platform_data(*, clear_images_dir: bool = True) -> dict:
    """
    Delete this tenant's local pipeline runs, drafts, assets, approvals, etc.
    """
    engine = get_engine(tenant_db_url())
    session = get_session_factory(engine)()
    counts: dict[str, int] = {}
    try:
        # Order matters for FKs
        pairs = [
            ("analytics", AnalyticsModel),
            ("published_posts", PublishedPostModel),
            ("approval_requests", ApprovalRequestModel),
            ("quality_checks", QualityCheckModel),
            ("visual_concepts", VisualConceptModel),
            ("generated_assets", GeneratedAssetModel),
            ("standalone_visuals", StandaloneVisualModel),
            ("content_drafts", ContentDraftModel),
            ("research_sources", ResearchSourceModel),
            ("topics", TopicModel),
            ("pipeline_runs", PipelineRunModel),
        ]
        for name, model in pairs:
            n = session.query(model).delete(synchronize_session=False)
            counts[name] = int(n or 0)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    images_removed = 0
    if clear_images_dir:
        img_dir = tenant_images_dir()
        if img_dir.exists():
            for f in img_dir.iterdir():
                if f.is_file():
                    try:
                        f.unlink()
                        images_removed += 1
                    except OSError as exc:
                        logger.warning("Could not delete %s: %s", f, exc)

    logger.info("Local platform cleared: %s images_removed=%s", counts, images_removed)
    return {"ok": True, "local_counts": counts, "local_images_removed": images_removed}

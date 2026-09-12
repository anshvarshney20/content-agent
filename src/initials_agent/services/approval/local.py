import uuid

from initials_agent.models.workflow import ApprovalRequest, ApprovalStatus
from initials_agent.repositories.approval import ApprovalRepository
from initials_agent.services.approval.base import ApprovalService


def caption_with_hashtags(caption: str, hashtags: list | None, limit: int = 2200) -> str:
    """Append stored hashtags to caption for publish (GUI already does this for display)."""
    text = (caption or "").rstrip()
    tags = [str(h).strip() for h in (hashtags or []) if str(h).strip()]
    if not tags:
        return text
    # Caption already includes hashtags
    if "#" in text:
        return text
    tag_line = " ".join(f"#{t.lstrip('#')}" for t in tags)
    out = f"{text}\n\n{tag_line}".strip()
    if len(out) > limit:
        # Keep as many tags as fit
        body_budget = max(0, limit - len(tag_line) - 2)
        out = f"{text[:body_budget].rstrip()}\n\n{tag_line}"[:limit]
    return out


def _asset_sort_key(asset) -> tuple:
    t = (getattr(asset, "asset_type", None) or "").lower()
    # instagram_carousel_3 → 3
    if "carousel_" in t:
        try:
            return (0, int(t.rsplit("_", 1)[-1]))
        except ValueError:
            return (0, 99)
    if "instagram" in t:
        return (1, 0)
    if "linkedin" in t:
        return (3, 0)
    return (2, 0)


def instagram_image_paths_from_assets(assets) -> list[str]:
    """Prefer ordered Instagram carousel slides; else any non-LinkedIn image; else first."""
    if not assets:
        return []
    ig = [
        a
        for a in assets
        if "instagram" in (getattr(a, "asset_type", None) or "").lower()
    ]
    chosen = ig if ig else [
        a
        for a in assets
        if "linkedin" not in (getattr(a, "asset_type", None) or "").lower()
    ]
    if not chosen:
        chosen = list(assets)
    chosen = sorted(chosen, key=_asset_sort_key)
    return [str(a.url) for a in chosen if getattr(a, "url", None)]


class LocalApprovalService(ApprovalService):
    def __init__(self, repo: ApprovalRepository):
        self.repo = repo
        
    def _map_to_domain(self, model) -> ApprovalRequest:
        draft = model.draft
        topic = draft.topic
        
        # Get latest quality check if any
        score = 0.0
        warnings = []
        if draft.quality_checks:
            qc = sorted(draft.quality_checks, key=lambda x: x.created_at, reverse=True)[0]
            score = qc.score
            warnings = qc.warnings
            
        image_paths = instagram_image_paths_from_assets(draft.assets if draft else [])
        image_path = image_paths[0] if image_paths else None
            
        return ApprovalRequest(
            id=model.id,
            draft_id=draft.id,
            topic=topic.title if topic else draft.title,
            linkedin_content=draft.linkedin_post,
            instagram_content=caption_with_hashtags(
                draft.instagram_caption,
                getattr(draft, "hashtags", None),
            ),
            image_path=image_path,
            image_paths=image_paths,
            quality_score=score,
            warnings=warnings,
            source_urls=draft.source_references,
            status=ApprovalStatus(model.status),
            reviewer_notes=model.reviewer_notes,
            generated_timestamp=model.created_at
        )
        
    def list_pending(self) -> list[ApprovalRequest]:
        models = self.repo.get_pending_requests()
        return [self._map_to_domain(m) for m in models]
        
    def get_request(self, request_id: uuid.UUID) -> ApprovalRequest | None:
        model = self.repo.get_request(request_id)
        if not model:
            return None
        return self._map_to_domain(model)
        
    def approve(self, request_id: uuid.UUID) -> None:
        self.repo.update_status(request_id, "approved")
        
    def reject(self, request_id: uuid.UUID, reason: str = None) -> None:
        self.repo.update_status(request_id, "rejected", reason)
        
    def regenerate(self, request_id: uuid.UUID, instructions: str = None) -> None:
        self.repo.update_status(request_id, "regeneration_requested", instructions)

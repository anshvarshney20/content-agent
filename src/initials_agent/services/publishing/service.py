import logging

from initials_agent.models.workflow import ApprovalRequest, ApprovalStatus
from initials_agent.repositories.publishing import PublishingRepository

from .instagram import InstagramPublisher
from .linkedin import LinkedInPublisher

logger = logging.getLogger(__name__)


class PublishingService:
    def __init__(self, linkedin: LinkedInPublisher, instagram: InstagramPublisher, repo: PublishingRepository):
        self.linkedin = linkedin
        self.instagram = instagram
        self.repo = repo

    async def publish_approved_request(
        self,
        req: ApprovalRequest,
        platforms: list[str] | None = None,
    ) -> dict[str, str]:
        if req.status != ApprovalStatus.APPROVED:
            raise ValueError(f"Cannot publish request with status {req.status}. Must be APPROVED.")

        already = {p.platform.lower() for p in self.repo.get_published_by_draft(req.draft_id)}
        targets = [p.lower() for p in (platforms or ["linkedin", "instagram"])]
        results: dict[str, str] = {}

        if "linkedin" in targets:
            if "linkedin" in already:
                results["linkedin"] = "already_published"
            else:
                try:
                    logger.info("Publishing to LinkedIn...")
                    li_id = await self.linkedin.publish(req)
                    self.repo.record_result(req.draft_id, "linkedin", li_id)
                    results["linkedin"] = li_id
                except Exception as e:
                    logger.error("Failed to publish to LinkedIn: %s", e)
                    results["linkedin_error"] = str(e)

        if "instagram" in targets:
            if "instagram" in already:
                results["instagram"] = "already_published"
            elif not (req.image_paths or req.image_path):
                results["instagram_error"] = "Instagram requires an image."
            else:
                try:
                    n = len(req.image_paths) if req.image_paths else 1
                    logger.info("Publishing to Instagram (%s slide%s)...", n, "" if n == 1 else "s")
                    ig_id = await self.instagram.publish(req)
                    self.repo.record_result(req.draft_id, "instagram", ig_id)
                    results["instagram"] = ig_id
                except Exception as e:
                    logger.error("Failed to publish to Instagram: %s", e)
                    results["instagram_error"] = str(e)

        return results

import logging
import uuid
from datetime import UTC, datetime

from initials_agent.db.models import (
    ContentDraftModel,
    GeneratedAssetModel,
    QualityCheckModel,
    TopicModel,
)
from initials_agent.models.content import Topic
from initials_agent.product.profile import load_profile
from initials_agent.services.approval.local import LocalApprovalService
from initials_agent.services.image_generation.service import ImageGenerationService
from initials_agent.services.quality.service import QualityControlService
from initials_agent.services.research.service import ResearchService
from initials_agent.services.strategist.service import ContentStrategistService
from initials_agent.services.visual.service import VisualContentService
from initials_agent.services.writer.service import ContentWriterService

logger = logging.getLogger(__name__)

class DailyContentPipeline:
    def __init__(self, 
                 research: ResearchService,
                 strategist: ContentStrategistService,
                 writer: ContentWriterService,
                 visual: VisualContentService,
                 image_gen: ImageGenerationService,
                 quality: QualityControlService,
                 approval: LocalApprovalService,
                 session):
        self.research = research
        self.strategist = strategist
        self.writer = writer
        self.visual = visual
        self.image_gen = image_gen
        self.quality = quality
        self.approval = approval
        self.session = session
        
    async def run(self, is_dry_run: bool = False) -> uuid.UUID | None:
        run_id = uuid.uuid4()
        logger.info(f"Starting daily pipeline. Run ID: {run_id}. Dry Run: {is_dry_run}")
        
        try:
            # Step 1 & 2: Research & Deduplicate
            logger.info("1. Executing research...")
            research_results = await self.research.conduct_research("AI Automation")
            if not research_results or not research_results.sources:
                raise RuntimeError("Research failed to return results.")
                
            # Step 3: Select topic
            logger.info("2. Selecting topic...")
            selection = self.strategist.select_topic([research_results])
            if not selection:
                raise RuntimeError("Topic selection failed.")
                
            topic = Topic(
                title=selection.selected_topic,
                description=selection.reason,
                is_approved=True
            )
            
            # Save Topic (Skip DB flush in dry run for isolation if needed, but SQLite is local. 
            # We will use an in-memory DB or rollback for strict dry-run, handled in the CLI.)
            topic_model = TopicModel(
                title=topic.title,
                description=topic.description,
                angle=selection.content_angle,
                score=selection.score
            )
            self.session.add(topic_model)
            self.session.flush()
            
            # Step 4: Generate content
            logger.info("3. Generating content...")
            # We must map the StrategistDecision back to the correct ResearchSource to build a minimal ResearchResult context.
            matching_source = next(
                (s for s in research_results.sources if s.url == selection.source_urls[0]), 
                None
            )
            if not matching_source:
                raise RuntimeError("Selected topic source not found in research results.")
                
            brand_config = load_profile().brand_config()
            from initials_agent.models.research import ResearchResult

            snippet = (getattr(matching_source, "snippet", None) or "").strip() or matching_source.title
            context_result = ResearchResult(
                query=research_results.query,
                summary=(
                    f"Article title: {matching_source.title}\n"
                    f"Article story/details: {snippet}\n"
                    f"Why this story was selected: {selection.reason}\n"
                    f"Marketing angle to develop: {selection.content_angle}"
                ),
                sources=[matching_source],
            )

            draft = await self.writer.write_draft(selection, context_result, brand_config)
            
            # Step 5 & 6: Generate visual concept & Generate image
            logger.info("4. Generating visual concepts and images...")
            assets = await self.visual.create_visuals(draft, ["LinkedIn", "Instagram"])
            if not assets:
                raise RuntimeError("Visual generation failed.")
                
            # Step 7: Quality check
            logger.info("5. Running quality checks...")
            quality_li = await self.quality.check_quality(draft, "linkedin")
            quality_ig = await self.quality.check_quality(draft, "instagram")
            
            lowest_score = min(quality_li.score, quality_ig.score)
            errors = quality_li.errors + quality_ig.errors
            
            if lowest_score < 80.0 or errors:
                logger.error(f"Quality check failed. Score: {lowest_score}. Errors: {errors}")
                raise ValueError(f"Content failed quality thresholds (Score: {lowest_score})")
                
            # Step 8 & 9: Save everything & Create approval request
            logger.info("6. Persisting payload and generating Approval Request...")
            
            draft_id = uuid.uuid4()
            
            if not is_dry_run:
                # Save Draft
                draft_model = ContentDraftModel(
                    id=draft_id,
                    topic_id=topic_model.id,
                    title=draft.title,
                    hook=draft.hook,
                    linkedin_post=draft.linkedin_post,
                    instagram_caption=draft.instagram_caption,
                    cta=draft.cta,
                    hashtags=draft.hashtags,
                    source_references=[str(u) for u in draft.source_references],
                    state="PENDING_APPROVAL"
                )
                self.session.add(draft_model)
                
                # Save quality checks
                qc_li_model = QualityCheckModel(
                    draft_id=draft_id,
                    passed=quality_li.passed,
                    status=quality_li.status.value,
                    score=quality_li.score,
                    errors=quality_li.errors,
                    warnings=quality_li.warnings,
                    improvements=quality_li.improvements,
                    checked_at=datetime.now(UTC)
                )
                qc_ig_model = QualityCheckModel(
                    draft_id=draft_id,
                    passed=quality_ig.passed,
                    status=quality_ig.status.value,
                    score=quality_ig.score,
                    errors=quality_ig.errors,
                    warnings=quality_ig.warnings,
                    improvements=quality_ig.improvements,
                    checked_at=datetime.now(UTC)
                )
                self.session.add_all([qc_li_model, qc_ig_model])
                
                # Save assets
                for a in assets:
                    asset_model = GeneratedAssetModel(
                        draft_id=draft_id,
                        url=str(a.url),
                        asset_type=a.asset_type
                    )
                    self.session.add(asset_model)
                
                self.session.flush()
                
                # Create Approval Request via LocalApprovalService
                app_req_id = self.approval.repo.submit_draft_for_approval(draft_id)
                self.session.commit()
                logger.info(f"Pipeline completed successfully. Approval Request ID: {app_req_id}")
                return app_req_id
            else:
                self.session.rollback()
                logger.info("Pipeline dry-run completed successfully.")
                return run_id
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}")
            if not is_dry_run:
                self.session.rollback()
            raise

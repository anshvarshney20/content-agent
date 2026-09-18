import logging
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel

from initials_agent.db.models import (
    ApprovalRequestModel,
    ContentDraftModel,
    GeneratedAssetModel,
    PipelineRunModel,
    QualityCheckModel,
    TopicModel,
)
from initials_agent.daily import DAILY_TECH_QUERY
from initials_agent.models.content import Topic
from initials_agent.pipeline_progress import (
    advance_stage,
    complete_all,
    complete_stage,
    init_progress,
    mark_failed,
    skip_stage,
    write_progress,
)
from initials_agent.product.profile import is_auto_publish, load_profile, platforms_for_mode
from initials_agent.services.analytics.service import AnalyticsService
from initials_agent.services.approval.local import LocalApprovalService
from initials_agent.services.image_generation.service import ImageGenerationService
from initials_agent.services.publishing.service import PublishingService
from initials_agent.services.quality.service import QualityControlService
from initials_agent.services.research.service import ResearchService
from initials_agent.services.strategist.service import ContentStrategistService
from initials_agent.services.visual.service import VisualContentService
from initials_agent.services.writer.service import ContentWriterService

logger = logging.getLogger(__name__)

class RunOptions(BaseModel):
    dry_run: bool = False
    force: bool = False
    topic: str | None = None
    niche_id: str | None = None
    pipeline_run_id: uuid.UUID | None = None
    no_image: bool = False
    no_publish: bool = False

class DailyContentAgent:
    def __init__(self, 
                 research: ResearchService,
                 strategist: ContentStrategistService,
                 writer: ContentWriterService,
                 visual: VisualContentService,
                 image_gen: ImageGenerationService,
                 quality: QualityControlService,
                 approval: LocalApprovalService,
                 publishing: PublishingService,
                 analytics: AnalyticsService,
                 session):
        self.research = research
        self.strategist = strategist
        self.writer = writer
        self.visual = visual
        self.image_gen = image_gen
        self.quality = quality
        self.approval = approval
        self.publishing = publishing
        self.analytics = analytics
        self.session = session

    async def run(self, options: RunOptions) -> uuid.UUID | None:
        run_id = uuid.uuid4()
        profile = load_profile()
        # Freeze category for THIS run (Settings value at start — ignores later edits)
        from initials_agent.product.niches import (
            NICHE_BY_ID,
            resolve_primary_terms,
            resolve_research_query,
        )

        niche_id = (options.niche_id or profile.active_niche_id or "ai_automation").strip()
        custom = profile.custom_niche_text if niche_id == "custom" else ""
        if niche_id == "custom" and options.topic:
            custom = options.topic
        niche = NICHE_BY_ID.get(niche_id) or NICHE_BY_ID["ai_automation"]
        niche_label = (
            f"Custom: {custom[:48]}" if niche_id == "custom" and custom else niche.label
        )
        target_topic = resolve_research_query(niche_id, custom) or DAILY_TECH_QUERY
        brand_config = profile.brand_config()
        brand_config["niche_label"] = niche_label

        logger.info(
            "Daily Content Agent run %s brand=%s niche=%s (%s) pipeline=%s",
            run_id,
            brand_config["name"],
            niche_id,
            niche_label,
            options.pipeline_run_id,
        )

        def _run_cancelled() -> bool:
            if not options.pipeline_run_id:
                return False
            row = self.session.query(PipelineRunModel).filter_by(id=options.pipeline_run_id).first()
            if not row:
                return True
            return row.status in ("cancelled", "failed")

        progress = init_progress(
            niche=niche_label,
            no_image=options.no_image,
            no_publish=options.no_publish,
        )

        def _progress(stage_id: str) -> None:
            advance_stage(progress, stage_id)
            write_progress(self.session, options.pipeline_run_id, progress)

        def _done(stage_id: str) -> None:
            complete_stage(progress, stage_id)
            write_progress(self.session, options.pipeline_run_id, progress)

        try:
            write_progress(self.session, options.pipeline_run_id, progress)
            if _run_cancelled():
                logger.info("Pipeline %s cancelled before start — aborting", options.pipeline_run_id)
                return None

            focus_terms = list(
                dict.fromkeys(
                    resolve_primary_terms(niche_id, custom)
                    + [t for t in target_topic.split() if len(t) > 2]
                )
            )
            logger.info("--- PHASE 1: GENERATION (%s: %s) ---", niche_label, target_topic)

            # RESEARCH (niche-specific feeds + filters)
            from initials_agent.providers.research.rss import RssResearchProvider
            from initials_agent.services.research.service import ResearchService

            _progress("research")
            research = ResearchService(RssResearchProvider(niche_id=niche_id))
            research_results = await research.conduct_research(target_topic)
            if not research_results or not research_results.sources:
                raise RuntimeError(
                    f"RESEARCH failed: No sources found for category “{niche_label}”. "
                    "Try again or pick Custom with clearer keywords."
                )
            _done("research")

            if _run_cancelled():
                logger.info("Pipeline %s cancelled after research — aborting", options.pipeline_run_id)
                return None

            # STRATEGY
            _progress("topic")
            selection = self.strategist.select_topic([research_results], focus_terms=focus_terms)
            if not selection:
                raise RuntimeError("STRATEGY failed: Topic selection rejected.")

            progress["topic_title"] = selection.selected_topic
            write_progress(self.session, options.pipeline_run_id, progress)

            topic = Topic(
                title=selection.selected_topic,
                description=f"[{niche_label}] {selection.reason}",
                is_approved=True,
            )
            topic_model = TopicModel(
                title=topic.title,
                description=topic.description,
                angle=selection.content_angle,
                score=selection.score
            )
            self.session.add(topic_model)
            self.session.flush()
            _done("topic")

            # CONTENT
            _progress("writing")
            matching_source = next((s for s in research_results.sources if s.url == selection.source_urls[0]), None)
            if not matching_source:
                raise RuntimeError("Selected topic source not found in research results.")
                
            from initials_agent.models.research import ResearchResult

            snippet = (getattr(matching_source, "snippet", None) or "").strip()
            if not snippet:
                # Fallback: pull the matching block from the aggregated research summary
                for block in (research_results.summary or "").split("\n\n"):
                    if matching_source.title in block:
                        snippet = block.strip()
                        break
            if not snippet:
                snippet = matching_source.title

            context_result = ResearchResult(
                query=research_results.query,
                summary=(
                    f"Article title: {matching_source.title}\n"
                    f"Article story/details: {snippet}\n"
                    f"Why this story was selected: {selection.reason}\n"
                    f"Marketing angle to develop: {selection.content_angle}\n"
                    f"Audience niche: {niche_label}"
                ),
                sources=[matching_source],
            )
            draft = await self.writer.write_draft(selection, context_result, brand_config)
            _done("writing")

            if _run_cancelled():
                logger.info("Pipeline %s cancelled before save — aborting", options.pipeline_run_id)
                self.session.rollback()
                return None

            # VISUAL & IMAGE — one Instagram image (Puter). No second full retry (keeps run ≤~5 min).
            assets = []
            if not options.no_image:
                _progress("visual")
                try:
                    assets = await self.visual.create_visuals(draft, ["Instagram"])
                    if not assets:
                        raise RuntimeError("Visual returned no assets")
                    _done("visual")
                except Exception as e:
                    logger.warning("Visual generation skipped so copy can still ship: %s", e)
                    skip_stage(progress, "visual", reason=str(e)[:120])
                    write_progress(self.session, options.pipeline_run_id, progress)

            if _run_cancelled():
                logger.info("Pipeline %s cancelled after visuals — aborting", options.pipeline_run_id)
                self.session.rollback()
                return None

            # QUALITY CONTROL — deterministic only (skips 2× OpenRouter LLM calls ≈ 1–3 min)
            _progress("quality")
            quality_li = await self.quality.check_quality(draft, "linkedin", use_llm=False)
            quality_ig = await self.quality.check_quality(draft, "instagram", use_llm=False)
            lowest_score = min(quality_li.score, quality_ig.score)
            errors = quality_li.errors + quality_ig.errors
            
            if lowest_score < 80.0 or errors:
                logger.warning("QUALITY flags (Score: %s): %s — saving draft for review", lowest_score, errors)
                draft_state = "NEEDS_REVISION"
            else:
                draft_state = "PENDING_APPROVAL"
            _done("quality")

            # APPROVAL / SAVE
            draft_id = uuid.uuid4()
            if not options.dry_run:
                _progress("save")
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
                    state=draft_state
                )
                self.session.add(draft_model)
                
                # Save quality checks
                qc_li_model = QualityCheckModel(
                    draft_id=draft_id, passed=quality_li.passed, status=quality_li.status.value,
                    score=quality_li.score, errors=quality_li.errors, warnings=quality_li.warnings,
                    improvements=quality_li.improvements, checked_at=datetime.now(UTC)
                )
                qc_ig_model = QualityCheckModel(
                    draft_id=draft_id, passed=quality_ig.passed, status=quality_ig.status.value,
                    score=quality_ig.score, errors=quality_ig.errors, warnings=quality_ig.warnings,
                    improvements=quality_ig.improvements, checked_at=datetime.now(UTC)
                )
                self.session.add_all([qc_li_model, qc_ig_model])
                
                # Save assets
                for a in assets:
                    asset_model = GeneratedAssetModel(draft_id=draft_id, url=str(a.url), asset_type=a.asset_type)
                    self.session.add(asset_model)
                self.session.flush()
                
                app_req_id = self.approval.repo.submit_draft_for_approval(draft_id)
                self.session.commit()
                logger.info(f"APPROVAL REQUEST generated: {app_req_id}")
                progress["draft_title"] = draft.title
                progress["draft_id"] = str(draft_id)
                write_progress(self.session, options.pipeline_run_id, progress)

                # Push draft + images to Supabase (Postgres + Storage)
                try:
                    from initials_agent.saas.sync import sync_local_draft_to_supabase

                    asset_paths = [(str(a.url), a.asset_type) for a in assets]
                    sync_result = await sync_local_draft_to_supabase(
                        local_draft_id=draft_id,
                        title=draft.title,
                        hook=draft.hook,
                        linkedin_post=draft.linkedin_post,
                        instagram_caption=draft.instagram_caption,
                        cta=draft.cta,
                        hashtags=draft.hashtags,
                        source_references=list(draft.source_references or []),
                        state=draft_state,
                        asset_paths=asset_paths,
                        business_name=profile.business_name,
                        topic_title=topic.title,
                        topic_description=topic.description,
                    )
                    if sync_result:
                        logger.info("Supabase sync ok: %s", sync_result.get("draft_id"))
                    else:
                        logger.warning(
                            "Supabase sync skipped (configure SUPABASE__* and sign up once for a brand)"
                        )
                except Exception as sync_exc:
                    logger.warning("Supabase sync failed (local draft still saved): %s", sync_exc)

                # Auto-publish modes: approve this draft immediately
                if (
                    not options.no_publish
                    and is_auto_publish(profile.publish_mode)
                    and draft_state == "PENDING_APPROVAL"
                ):
                    try:
                        self.approval.approve(app_req_id)
                        self.session.commit()
                        logger.info("Auto-approved draft for publish mode=%s", profile.publish_mode)
                    except Exception as e:
                        logger.warning("Auto-approve failed: %s", e)
                _done("save")

            # PHASE 2: PUBLISHING
            logger.info("--- PHASE 2: PUBLISHING ---")
            if not options.no_publish and not options.dry_run:
                _progress("publish")
                platforms = platforms_for_mode(profile.publish_mode)
                if not platforms:
                    platforms = ["linkedin", "instagram"]

                approved_requests = self.session.query(ApprovalRequestModel).filter_by(status="approved").all()
                for req_model in approved_requests:
                    domain_req = self.approval._map_to_domain(req_model)
                    try:
                        result = await self.publishing.publish_approved_request(domain_req, platforms=platforms)
                        logger.info("PUBLISH result for %s: %s", req_model.id, result)
                    except Exception as e:
                        logger.error("PUBLISH failed for request %s: %s", req_model.id, e)
                _done("publish")

            # PHASE 3: ANALYTICS & LEARNING
            logger.info("--- PHASE 3: ANALYTICS & LEARNING ---")
            if not options.dry_run:
                await self.analytics.sync_all()
                try:
                    profile = await self.analytics.generate_report()
                    logger.info(f"LEARNING successful. Profile updated: {profile.id}")
                except ValueError as e:
                    # Expected if insufficient data
                    logger.info(f"LEARNING skipped: {e}")

            complete_all(progress)
            write_progress(self.session, options.pipeline_run_id, progress)

            if options.dry_run:
                self.session.rollback()
                logger.info("DRY-RUN completed. Rollback applied.")
                return run_id

            return draft_id

        except Exception as e:
            logger.error(f"AGENT RUN FAILED: {e}")
            try:
                mark_failed(progress, str(e))
                write_progress(self.session, options.pipeline_run_id, progress)
            except Exception:
                pass
            if not options.dry_run:
                self.session.rollback()
            raise

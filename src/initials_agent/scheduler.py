import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from initials_agent.config import get_settings
from initials_agent.db.models import PipelineRunModel
from initials_agent.db.session import get_engine, get_session_factory
from initials_agent.agent import RunOptions

logger = logging.getLogger(__name__)

DB_URL = "sqlite:///initials_agent.db"


class Scheduler:
    """Daily loop that opens short-lived DB sessions (never holds a lock between ticks)."""

    def __init__(self, build_agent_fn=None):
        from initials_agent.runtime import build_agent

        self._build_agent = build_agent_fn or build_agent
        self.settings = get_settings().scheduling
        self._reload_schedule()
        self.running = False

    def _reload_schedule(self):
        from initials_agent.product.profile import load_profile

        profile = load_profile()
        tz_name = profile.timezone or self.settings.timezone
        time_str = profile.schedule_time or self.settings.publish_time
        self.tz = ZoneInfo(tz_name)
        h, m = time_str.split(":")
        self.schedule_hour = int(h)
        self.schedule_minute = int(m)
        self.schedule_enabled = bool(profile.schedule_enabled)

    async def start(self):
        self.running = True
        self._reload_schedule()
        logger.info(
            "Scheduler started. Daily run time: %02d:%02d %s (enabled=%s)",
            self.schedule_hour,
            self.schedule_minute,
            self.tz,
            self.schedule_enabled,
        )

        while self.running:
            try:
                self._reload_schedule()
                if self.schedule_enabled:
                    await self._check_schedule()
                    await self._publish_approved()
            except Exception as e:
                logger.error("Scheduler loop error: %s", e)

            for _ in range(60):
                if not self.running:
                    break
                await asyncio.sleep(1)

    async def stop(self):
        logger.info("Scheduler shutting down gracefully...")
        self.running = False

    def _session(self):
        engine = get_engine(DB_URL)
        return get_session_factory(engine)()

    async def _check_schedule(self):
        now = datetime.now(self.tz)
        run_date_str = now.strftime("%Y-%m-%d")

        if now.hour < self.schedule_hour or (
            now.hour == self.schedule_hour and now.minute < self.schedule_minute
        ):
            return

        session = self._session()
        try:
            run_record = session.query(PipelineRunModel).filter_by(run_date=run_date_str).first()
            should_run = False
            if not run_record:
                run_record = PipelineRunModel(run_date=run_date_str, status="running", retry_count=0)
                session.add(run_record)
                session.commit()
                session.refresh(run_record)
                should_run = True
            elif run_record.status == "failed" and run_record.retry_count < 3:
                logger.info(
                    "Retrying failed run for %s (Attempt %s/3)",
                    run_date_str,
                    run_record.retry_count + 1,
                )
                run_record.status = "running"
                run_record.retry_count += 1
                session.commit()
                should_run = True
            run_id = run_record.id if should_run else None
        finally:
            session.close()

        if run_id:
            await self._run_pipeline(run_id)

    async def _run_pipeline(self, run_id):
        from initials_agent.product.profile import load_profile

        session = self._session()
        try:
            profile = load_profile()
            run_record = session.query(PipelineRunModel).filter_by(id=run_id).first()
            if not run_record:
                return
            logger.info(
                "Executing daily content pipeline for %s (brand=%s niche=%s)...",
                run_record.run_date,
                profile.business_name or "unset",
                profile.niche_label(),
            )
            agent = self._build_agent(session)
            from initials_agent.product.profile import is_auto_publish

            no_publish = not is_auto_publish(profile.publish_mode)
            opts = RunOptions(
                dry_run=False,
                topic=profile.research_query(),
                niche_id=profile.active_niche_id,
                pipeline_run_id=run_id,
                no_image=False,
                no_publish=no_publish,
            )
            try:
                await agent.run(opts)
                run_record = session.query(PipelineRunModel).filter_by(id=run_id).first()
                if run_record and run_record.status == "running":
                    run_record.status = "success"
                    session.commit()
                logger.info("Daily content pipeline execution successful.")
            except Exception as e:
                logger.error("Pipeline execution failed: %s", e)
                run_record = session.query(PipelineRunModel).filter_by(id=run_id).first()
                if run_record and run_record.status == "running":
                    run_record.status = "failed"
                    run_record.logs = str(e)
                    session.commit()
        finally:
            session.close()

    async def _publish_approved(self):
        from initials_agent.db.models import ApprovalRequestModel
        from initials_agent.services.approval.local import LocalApprovalService

        session = self._session()
        try:
            agent = self._build_agent(session)
            approved_requests = (
                session.query(ApprovalRequestModel).filter_by(status="approved").all()
            )
            for req_model in approved_requests:
                existing = agent.publishing.repo.get_published_by_draft(req_model.draft_id)
                if existing:
                    continue
                try:
                    logger.info("Found approved request %s. Publishing...", req_model.id)
                    local_svc = LocalApprovalService(agent.approval.repo)
                    domain_req = local_svc._map_to_domain(req_model)
                    await agent.publishing.publish_approved_request(domain_req)
                    logger.info("Successfully published request %s", req_model.id)
                except Exception as e:
                    logger.error("Failed to publish request %s: %s", req_model.id, e)
        finally:
            session.close()

    async def run_now(self):
        now = datetime.now(self.tz)
        run_date_str = now.strftime("%Y-%m-%d-%H%M%S")
        session = self._session()
        try:
            run_record = PipelineRunModel(
                run_date=f"forced-{run_date_str}", status="running", retry_count=0
            )
            session.add(run_record)
            session.commit()
            run_id = run_record.id
        finally:
            session.close()
        await self._run_pipeline(run_id)

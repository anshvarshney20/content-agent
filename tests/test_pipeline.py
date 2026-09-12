import pytest
import os
import uuid
from initials_agent.db.session import get_engine, get_session_factory
from initials_agent.db.models import Base
from initials_agent.services.research.service import ResearchService
from initials_agent.providers.research.mock import MockResearchProvider
from initials_agent.repositories.topics import TopicRepository
from initials_agent.services.strategist.service import ContentStrategistService
from initials_agent.providers.llm.mock import MockLLMProvider
from initials_agent.services.writer.service import ContentWriterService
from initials_agent.providers.image.mock import MockImageProvider
from initials_agent.services.image_generation.service import ImageGenerationService
from initials_agent.services.visual.service import VisualContentService
from initials_agent.services.quality.service import QualityControlService
from initials_agent.repositories.approval import ApprovalRepository
from initials_agent.services.approval.local import LocalApprovalService
from initials_agent.agent import DailyContentAgent, RunOptions
from initials_agent.repositories.publishing import PublishingRepository
from initials_agent.services.publishing.service import PublishingService
from initials_agent.providers.publishing.mock import MockSocialPublisher
from initials_agent.repositories.analytics import AnalyticsRepository
from initials_agent.services.analytics.service import AnalyticsService
from initials_agent.providers.analytics.mock import MockAnalyticsProvider
import shutil

@pytest.fixture
def session():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = get_session_factory(engine)
    s = Session()
    yield s
    s.close()
    
@pytest.fixture
def output_dir():
    path = os.path.join(os.getcwd(), "test_pipeline_images")
    os.makedirs(path, exist_ok=True)
    yield path
    shutil.rmtree(path)

@pytest.fixture
def agent(session, output_dir):
    research_srv = ResearchService(MockResearchProvider())
    topic_repo = TopicRepository(session)
    strategist_srv = ContentStrategistService(topic_repo)
    llm_prov = MockLLMProvider()
    writer_srv = ContentWriterService(llm_prov)
    img_prov = MockImageProvider()
    img_srv = ImageGenerationService(img_prov, output_dir)
    vis_srv = VisualContentService(llm_prov, img_srv)
    qual_srv = QualityControlService(llm_prov)
    app_repo = ApprovalRepository(session)
    app_srv = LocalApprovalService(app_repo)
    pub_srv = PublishingService(MockSocialPublisher(), MockSocialPublisher(), PublishingRepository(session))
    analytics_srv = AnalyticsService(MockAnalyticsProvider(), MockAnalyticsProvider(), AnalyticsRepository(session), llm_prov)
    
    return DailyContentAgent(
        research=research_srv,
        strategist=strategist_srv,
        writer=writer_srv,
        visual=vis_srv,
        image_gen=img_srv,
        quality=qual_srv,
        approval=app_srv,
        publishing=pub_srv,
        analytics=analytics_srv,
        session=session
    )

@pytest.mark.asyncio
async def test_agent_success(agent):
    opts = RunOptions(dry_run=True)
    run_id = await agent.run(opts)
    assert run_id is not None
    
@pytest.mark.asyncio
async def test_agent_success_live(agent):
    opts = RunOptions(dry_run=False, no_publish=True)
    app_req_id = await agent.run(opts)
    assert app_req_id is not None
    
@pytest.mark.asyncio
async def test_agent_continues_when_visuals_fail(agent):
    class FailingVisualContentService:
        async def create_visuals(self, draft, platforms):
            raise RuntimeError("Visual generation failed.")

    agent.visual = FailingVisualContentService()
    opts = RunOptions(dry_run=True, no_publish=True)
    run_id = await agent.run(opts)
    assert run_id is not None

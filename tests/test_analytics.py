import pytest
import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock

from initials_agent.db.session import get_engine, get_session_factory
from initials_agent.db.models import Base, PublishedPostModel, AnalyticsModel, ContentDraftModel, TopicModel
from initials_agent.repositories.analytics import AnalyticsRepository
from initials_agent.services.analytics.service import AnalyticsService
from initials_agent.providers.analytics.mock import MockAnalyticsProvider
from initials_agent.providers.llm.mock import MockLLMProvider

@pytest.fixture
def session():
    engine = get_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = get_session_factory(engine)
    s = Session()
    yield s
    s.close()

@pytest.fixture
def analytics_service(session):
    repo = AnalyticsRepository(session)
    li_prov = MockAnalyticsProvider()
    ig_prov = MockAnalyticsProvider()
    llm = MockLLMProvider()
    return AnalyticsService(li_prov, ig_prov, repo, llm)

def create_mock_published_post(session, platform="linkedin"):
    topic = TopicModel(title="Analytics Test")
    session.add(topic)
    
    draft = ContentDraftModel(
        topic=topic,
        title="Test Post",
        hook="Test Hook",
        linkedin_post="Content",
        instagram_caption="Content",
        cta="Click",
        hashtags=["#test"],
        source_references=["http://example.com"],
        state="PUBLISHED"
    )
    session.add(draft)
    
    post = PublishedPostModel(
        draft=draft,
        platform=platform,
        external_id=str(uuid.uuid4()),
        url="http://example.com/post",
        published_at=datetime.now(timezone.utc)
    )
    session.add(post)
    session.commit()
    return post

@pytest.mark.asyncio
async def test_analytics_sync(analytics_service, session):
    # Setup some published posts
    create_mock_published_post(session, "linkedin")
    create_mock_published_post(session, "instagram")
    
    await analytics_service.sync_all()
    
    analytics = session.query(AnalyticsModel).all()
    assert len(analytics) == 2
    assert analytics[0].impressions > 0
    assert analytics[0].engagement_rate > 0.0

@pytest.mark.asyncio
async def test_analytics_report_insufficient_data(analytics_service, session):
    # Only 2 posts, should reject reporting (requires 5)
    create_mock_published_post(session, "linkedin")
    create_mock_published_post(session, "instagram")
    
    with pytest.raises(ValueError, match="Insufficient data for analytics report. Need at least 5 posts."):
        await analytics_service.generate_report()

@pytest.mark.asyncio
async def test_analytics_report_success(analytics_service, session):
    # Create 5 posts to satisfy the requirement
    for _ in range(5):
        post = create_mock_published_post(session, "linkedin")
        # Add some analytics data
        snap = AnalyticsModel(
            post_id=post.id,
            impressions=1000,
            engagement_rate=0.05,
            recorded_at=datetime.now(timezone.utc)
        )
        session.add(snap)
    session.commit()
    
    profile = await analytics_service.generate_report()
    
    assert profile.is_active is True
    assert "AI Agents" in profile.strongest_topics
    
    # Verify DB saved it
    from initials_agent.db.models import ContentStrategyProfileModel
    profiles = session.query(ContentStrategyProfileModel).all()
    assert len(profiles) == 1
    assert profiles[0].is_active is True

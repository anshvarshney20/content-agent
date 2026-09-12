import pytest
from datetime import datetime, timezone, timedelta
from initials_agent.repositories.database import Database
from initials_agent.repositories.topics import TopicRepository
from initials_agent.services.strategist.service import ContentStrategistService, StrategistDecision
from initials_agent.models.research import ResearchResult, ResearchSource

import tempfile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from initials_agent.db.models import Base

@pytest.fixture
def memory_repo():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield TopicRepository(session)
    session.close()
    
@pytest.fixture
def strategist(memory_repo):
    return ContentStrategistService(memory_repo)

def test_scoring_determinism(strategist):
    now = datetime.now(timezone.utc)
    source = ResearchSource(
        url="https://test.com",
        title="AI Automation in Startups",
        published_date=now - timedelta(hours=12),
        credibility_score=0.9
    )
    score1 = strategist.score_source(source, [])
    score2 = strategist.score_source(source, [])
    assert score1 == score2
    assert score1 > 0

def test_stale_and_missing_metadata(strategist):
    now = datetime.now(timezone.utc)
    # Good fresh source
    source1 = ResearchSource(url="https://test.com/1", title="AI", published_date=now, credibility_score=0.9)
    # Stale source
    source2 = ResearchSource(url="https://test.com/2", title="AI", published_date=now - timedelta(days=10), credibility_score=0.9)
    # Missing date source
    source3 = ResearchSource(url="https://test.com/3", title="AI", published_date=None, credibility_score=0.9)
    
    s1 = strategist.score_source(source1, [])
    s2 = strategist.score_source(source2, [])
    s3 = strategist.score_source(source3, [])
    
    assert s1 > s2 # Freshness gets +20, stale gets 0
    assert s2 > s3 # Missing date gets -10
    
def test_poor_quality_sources(strategist):
    now = datetime.now(timezone.utc)
    good = ResearchSource(url="https://test.com/1", title="AI", published_date=now, credibility_score=0.9)
    poor = ResearchSource(url="https://test.com/2", title="AI", published_date=now, credibility_score=0.2)
    
    assert strategist.score_source(good, []) > strategist.score_source(poor, [])
    assert strategist.score_source(poor, []) < 10 # Poor quality penalty reduces score significantly
    
def test_duplicate_detection(strategist, memory_repo):
    now = datetime.now(timezone.utc)
    source = ResearchSource(url="https://test.com/1", title="Amazing AI Startup", published_date=now, credibility_score=0.9)
    
    score_first = strategist.score_source(source, [])
    
    # Record it as recent
    memory_repo.record_topic("Amazing AI Startup", "angle", score_first)
    recent = memory_repo.get_recent_topics()
    
    score_second = strategist.score_source(source, recent)
    
    assert score_first > score_second
    assert score_second < score_first - 30

def test_select_strongest_topic(strategist):
    now = datetime.now(timezone.utc)
    res = ResearchResult(
        query="test",
        summary="This summary is definitely long enough now.",
        sources=[
            ResearchSource(url="https://test.com/poor", title="Rumor: AI fails", published_date=now, credibility_score=0.3),
            ResearchSource(url="https://test.com/good", title="How AI Automation helps Startups", published_date=now, credibility_score=0.95)
        ]
    )
    decision = strategist.select_topic([res])
    assert decision.selected_topic == "How AI Automation helps Startups"
    assert "educational post" in decision.recommended_format or "business use case" in decision.recommended_format

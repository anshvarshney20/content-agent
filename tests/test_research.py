import pytest
from datetime import datetime, timezone, timedelta
from initials_agent.providers.research.base import RawSearchResult
from initials_agent.providers.research.mock import MockResearchProvider
from initials_agent.services.research.service import ResearchService
from initials_agent.agents.researcher import ResearchAgent

class DeterministicMockProvider(MockResearchProvider):
    async def search(self, query: str, limit: int = 5):
        now = datetime.now(timezone.utc)
        return [
            RawSearchResult(
                title="Good News", url="https://test.com/1", summary="Sum 1",
                published_date=now - timedelta(days=1), source_domain="test.com"
            ),
            RawSearchResult(
                title="Old News", url="https://test.com/2", summary="Sum 2",
                published_date=now - timedelta(days=60), source_domain="test.com"
            ),
            RawSearchResult(
                title="Good News", url="https://test.com/1", summary="Sum 1",
                published_date=now - timedelta(days=1), source_domain="test.com"
            ),
            RawSearchResult(
                title="Recent News", url="https://test.com/3", summary="Sum 3",
                published_date=now - timedelta(hours=5), source_domain="test.com"
            )
        ][:limit]

@pytest.mark.asyncio
async def test_research_service_deduplication_and_staleness():
    provider = DeterministicMockProvider()
    service = ResearchService(provider=provider)
    result = await service.conduct_research("test query", limit=5)
    
    # Should reject the duplicate and the old news (60 days > 30 days default)
    # Expected sources: https://test.com/1 and https://test.com/3
    assert len(result.sources) == 2
    urls = [str(s.url) for s in result.sources]
    assert "https://test.com/1" in urls
    assert "https://test.com/3" in urls
    assert "https://test.com/2" not in urls

@pytest.mark.asyncio
async def test_research_agent():
    agent = ResearchAgent(service=ResearchService(provider=DeterministicMockProvider()))
    result = await agent.run_daily_research(limit=5)
    assert len(result.sources) == 2
    assert "Sum 1" in result.summary
    assert "Sum 3" in result.summary

from initials_agent.models import ResearchResult
from initials_agent.providers.research.mock import MockResearchProvider
from initials_agent.services.research.service import ResearchService


class ResearchAgent:
    def __init__(self, service: ResearchService = None):
        if service is None:
            # In a production setting, this would be injected based on configuration
            provider = MockResearchProvider()
            self.service = ResearchService(provider=provider)
        else:
            self.service = service
            
    async def run_daily_research(self, limit: int = 5) -> ResearchResult:
        query = "artificial intelligence OR generative AI OR developer tools OR cybersecurity OR automation"
        return await self.service.conduct_research(query, limit=limit)


from initials_agent.models.research import ResearchResult
from initials_agent.repositories.database import Database
from initials_agent.repositories.topics import TopicRepository
from initials_agent.services.strategist.service import (
    ContentStrategistService,
    StrategistDecision,
)


class StrategistAgent:
    def __init__(self, service: ContentStrategistService = None):
        if service is None:
            db = Database()
            repo = TopicRepository(db)
            self.service = ContentStrategistService(repo)
        else:
            self.service = service
            
    def strategize(self, results: list[ResearchResult]) -> StrategistDecision:
        return self.service.select_topic(results)

from initials_agent.models.content import ContentDraft
from initials_agent.models.research import ResearchResult
from initials_agent.product.profile import load_profile
from initials_agent.providers.llm.mock import MockLLMProvider
from initials_agent.services.strategist.service import StrategistDecision
from initials_agent.services.writer.service import ContentWriterService


class WriterAgent:
    def __init__(self, service: ContentWriterService = None):
        if service is None:
            llm = MockLLMProvider()
            self.service = ContentWriterService(llm=llm)
        else:
            self.service = service

    async def run_writer(self, decision: StrategistDecision, research: ResearchResult) -> ContentDraft:
        # Always use the customer brand profile — never a single hardcoded company
        brand_config = load_profile().brand_config()
        return await self.service.write_draft(decision, research, brand_config)

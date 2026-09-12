from initials_agent.models.content import ContentDraft
from initials_agent.models.workflow import QualityCheck
from initials_agent.providers.llm.mock import MockLLMProvider
from initials_agent.services.quality.service import QualityControlService


class QualityAgent:
    def __init__(self, service: QualityControlService = None):
        if service is None:
            llm = MockLLMProvider()
            self.service = QualityControlService(llm=llm)
        else:
            self.service = service
            
    async def review_content(self, draft: ContentDraft, platform: str) -> QualityCheck:
        return await self.service.check_quality(draft, platform)

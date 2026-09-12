import os

from initials_agent.models.content import ContentDraft
from initials_agent.providers.image.mock import MockImageProvider
from initials_agent.providers.llm.mock import MockLLMProvider
from initials_agent.services.image_generation.service import ImageGenerationService
from initials_agent.services.visual.service import VisualContentService


class VisualAgent:
    def __init__(self, service: VisualContentService = None):
        if not service:
            provider = MockImageProvider()
            img_service = ImageGenerationService(provider, os.path.join(os.getcwd(), "output", "images"))
            self.service = VisualContentService(MockLLMProvider(), img_service)
        else:
            self.service = service
            
    async def run_visuals(self, draft: ContentDraft, platforms: list[str]) -> ContentDraft:
        await self.service.create_visuals(draft, platforms)
        return draft

import pytest
from initials_agent.models.content import ContentDraft, ContentState
from initials_agent.providers.llm.mock import MockLLMProvider
from initials_agent.providers.image.mock import MockImageProvider
from initials_agent.services.visual.service import VisualContentService
from initials_agent.services.image_generation.service import ImageGenerationService
from initials_agent.agents.visual import VisualAgent

@pytest.fixture
def dummy_draft():
    return ContentDraft(
        title="AI Automation in Startups",
        hook="Are you wasting time on manual workflows?",
        linkedin_post="Automation is the key to scaling startups efficiently without hiring rapidly.",
        instagram_caption="Scale your startup with AI automation. #startup #ai",
        cta="Learn how we can automate your processes.",
        hashtags=["ai", "startups"],
        source_references=["https://example.com/source"]
    )

@pytest.mark.asyncio
async def test_visual_service_success(dummy_draft):
    import os
    llm = MockLLMProvider()
    provider = MockImageProvider()
    img_service = ImageGenerationService(provider, os.path.join(os.getcwd(), "test_images_output"))
    service = VisualContentService(llm=llm, image_service=img_service)
    
    assets = await service.create_visuals(dummy_draft, ["LinkedIn", "Instagram"])
    
    assert len(assets) == 2
    assert assets[0].asset_type == "linkedin_image"
    assert assets[1].asset_type == "instagram_image"
    
    # Check if the MockImageProvider returned correctly formatted urls using the concept aspect ratio
    assert str(assets[0].url).endswith(".png")
    
    assert dummy_draft.visual_concept is not None
    assert dummy_draft.visual_concept.color_palette == "Black, electric blue, neon purple"

@pytest.mark.asyncio
async def test_visual_retry_failure(dummy_draft):
    class AlwaysFailLLM(MockLLMProvider):
        async def generate_json(self, prompt, system, schema):
            raise ValueError("Always fail visual")
            
    import os
    llm = AlwaysFailLLM()
    provider = MockImageProvider()
    img_service = ImageGenerationService(provider, os.path.join(os.getcwd(), "test_images_output"))
    service = VisualContentService(llm=llm, image_service=img_service, max_retries=2)
    
    with pytest.raises(RuntimeError, match="Failed to generate visual concept"):
        await service.create_visuals(dummy_draft, ["Instagram"])

@pytest.mark.asyncio
async def test_visual_agent(dummy_draft):
    agent = VisualAgent()
    draft = await agent.run_visuals(dummy_draft, ["LinkedIn"])
    
    assert len(draft.assets) == 1
    assert draft.visual_concept is not None
    assert str(draft.assets[0].url).endswith(".png")

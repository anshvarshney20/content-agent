import pytest
from initials_agent.models.content import ContentDraft, VisualConcept
from initials_agent.providers.llm.mock import MockLLMProvider
from initials_agent.services.quality.service import QualityControlService
from initials_agent.agents.quality import QualityAgent

@pytest.fixture
def perfect_draft():
    return ContentDraft(
        title="Perfect Title",
        hook="Perfect hook that is long enough",
        linkedin_post="A sufficiently long LinkedIn post that meets the minimum length requirement easily without issues.",
        instagram_caption="A sufficiently long Instagram caption that meets the minimum length requirement easily without issues.",
        cta="Learn more.",
        hashtags=["tech", "ai"],
        visual_concept=VisualConcept(
            aspect_ratio="1200x1200", composition="C", headline="H", supporting_text="S", visual_subject="VS",
            environment="E", lighting="L", color_palette="CP", typography="T", negative_prompt="NP", brand_requirements="BR"
        ),
        source_references=["https://example.com/source"]
    )

@pytest.mark.asyncio
async def test_quality_pass(perfect_draft):
    service = QualityControlService(llm=MockLLMProvider())
    qc = await service.check_quality(perfect_draft, "linkedin")
    assert qc.passed is True
    assert qc.score > 90
    assert not qc.errors

@pytest.mark.asyncio
async def test_quality_missing_sources(perfect_draft):
    perfect_draft.source_references = []
    service = QualityControlService(llm=MockLLMProvider())
    qc = await service.check_quality(perfect_draft, "linkedin")
    assert qc.passed is False
    assert "No source references provided." in qc.errors

@pytest.mark.asyncio
async def test_quality_platform_limits(perfect_draft):
    perfect_draft.linkedin_post = "A" * 3001
    service = QualityControlService(llm=MockLLMProvider())
    qc = await service.check_quality(perfect_draft, "linkedin")
    assert qc.passed is False
    assert "LinkedIn post exceeds 3000 characters." in qc.errors

@pytest.mark.asyncio
async def test_quality_hashtag_quality(perfect_draft):
    perfect_draft.hashtags = []
    service = QualityControlService(llm=MockLLMProvider())
    qc = await service.check_quality(perfect_draft, "linkedin")
    assert qc.passed is False
    assert "Missing hashtags." in qc.errors

@pytest.mark.asyncio
async def test_quality_image_dimensions(perfect_draft):
    perfect_draft.visual_concept.aspect_ratio = "999x999"
    service = QualityControlService(llm=MockLLMProvider())
    qc = await service.check_quality(perfect_draft, "linkedin")
    assert qc.passed is False
    assert "Invalid image dimensions: 999x999" in qc.errors

@pytest.mark.asyncio
async def test_quality_llm_failure(perfect_draft):
    # LLM returns unsupported stats error
    class FailLLM(MockLLMProvider):
        async def generate_json(self, prompt, sys, schema):
            return schema.model_validate({
                "factual_consistency_score": 50,
                "unsupported_statistics": True,
                "invented_quotes": True,
                "brand_voice_score": 90,
                "brand_visual_requirements_met": False,
                "grammar_score": 100,
                "misleading_claims": True,
                "excessive_promotional": True,
                "cta_quality_score": 90,
                "feedback_notes": ["Bad."],
                "duplicate_content_detected": True
            })
    
    service = QualityControlService(llm=FailLLM())
    qc = await service.check_quality(perfect_draft, "linkedin")
    assert qc.passed is False
    assert "LLM detected unsupported statistics." in qc.errors
    assert "LLM detected invented quotes." in qc.errors
    assert "LLM detected misleading claims." in qc.errors
    assert "Duplicate content detected by LLM." in qc.errors

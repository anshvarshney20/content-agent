import pytest
from initials_agent.services.strategist.service import StrategistDecision
from initials_agent.models.research import ResearchResult, ResearchSource
from initials_agent.providers.llm.mock import MockLLMProvider
from initials_agent.services.writer.service import ContentWriterService
from initials_agent.agents.writer import WriterAgent
from initials_agent.models.content import ContentState

@pytest.fixture
def dummy_inputs():
    decision = StrategistDecision(
        selected_topic="AI Agents in production",
        reason="Good topic",
        score=50.0,
        source_urls=["https://test.com"],
        content_angle="Technical breakdown",
        recommended_format="carousel"
    )
    research = ResearchResult(
        query="ai",
        summary="summary of AI agents taking over.",
        sources=[ResearchSource(url="https://test.com", title="Title", credibility_score=0.9)]
    )
    return decision, research

@pytest.mark.asyncio
async def test_writer_success(dummy_inputs):
    decision, research = dummy_inputs
    llm = MockLLMProvider()
    service = ContentWriterService(llm=llm)
    
    draft = await service.write_draft(decision, research, {"name": "Test"})
    assert draft.title == "Mock Title for Agent"
    assert draft.state == ContentState.DRAFT
    assert len(draft.hashtags) == 2
    assert llm.attempts == 1

@pytest.mark.asyncio
async def test_writer_retry_success(dummy_inputs):
    decision, research = dummy_inputs
    llm = MockLLMProvider(should_fail_first_time=True)
    service = ContentWriterService(llm=llm, max_retries=3)
    
    draft = await service.write_draft(decision, research, {"name": "Test"})
    assert llm.attempts == 2 # Failed first, succeeded second
    assert draft.title == "Mock Title for Agent"

@pytest.mark.asyncio
async def test_writer_retry_failure(dummy_inputs):
    decision, research = dummy_inputs
    
    class AlwaysFailLLM(MockLLMProvider):
        async def generate_json(self, prompt, system, schema):
            raise ValueError("Always fail")
            
    llm = AlwaysFailLLM()
    service = ContentWriterService(llm=llm, max_retries=2)
    
    with pytest.raises(RuntimeError, match="Failed to generate valid content"):
        await service.write_draft(decision, research, {"name": "Test"})
        
@pytest.mark.asyncio
async def test_writer_agent(dummy_inputs):
    decision, research = dummy_inputs
    agent = WriterAgent()
    draft = await agent.run_writer(decision, research)
    assert draft.title == "Mock Title for Agent"

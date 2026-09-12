import pytest
import uuid
from pydantic import ValidationError
from initials_agent.models import (
    Topic, ResearchSource, ResearchResult, ContentDraft, VisualConcept,
    GeneratedAsset, LinkedInPost, InstagramPost, PublishedPost, PostAnalytics,
    QualityCheck, ApprovalRequest,
    ContentState, SocialPlatform, QualityStatus, ApprovalStatus
)

def test_topic_valid():
    topic = Topic(title="Valid Title", description="This is a valid description of the topic.")
    assert topic.title == "Valid Title"
    assert not topic.is_approved

def test_topic_invalid():
    with pytest.raises(ValidationError):
        Topic(title="sh", description="too short")

def test_research_source():
    source = ResearchSource(url="https://example.com/ai-trends", title="AI Trends", credibility_score=0.85)
    assert str(source.url) == "https://example.com/ai-trends"
    
    with pytest.raises(ValidationError):
        ResearchSource(url="not-a-url", title="Title", credibility_score=0.5)

    with pytest.raises(ValidationError):
        ResearchSource(url="https://example.com", title="Title", credibility_score=1.5)

def test_research_result():
    source = ResearchSource(url="https://example.com/1", title="Source 1", credibility_score=0.9)
    res = ResearchResult(query="AI in 2026", summary="AI is advancing rapidly.", sources=[source])
    assert len(res.sources) == 1

def test_content_draft():
    draft = ContentDraft(
        title="AI Automation in Startups",
        hook="Are you wasting time on manual workflows?",
        linkedin_post="Automation is the key to scaling startups efficiently without hiring rapidly.",
        instagram_caption="Scale your startup with AI automation. #startup #ai",
        cta="Learn how we can automate your processes.",
        hashtags=["ai", "startups"],
        source_references=["https://example.com/source"]
    )
    assert draft.state == ContentState.DRAFT
    
    # Test JSON serialization/deserialization
    draft_json = draft.model_dump_json()
    draft_restored = ContentDraft.model_validate_json(draft_json)
    assert draft_restored.title == draft.title
    assert draft_restored.state == ContentState.DRAFT

def test_linkedin_post():
    post = LinkedInPost(text="This is a post for LinkedIn.")
    assert post.platform == SocialPlatform.LINKEDIN
    
def test_instagram_post():
    with pytest.raises(ValidationError):
        # Missing media urls
        InstagramPost(caption="Check out this image!")
        
    post = InstagramPost(caption="Check out this image!", media_urls=["https://example.com/image.jpg"])
    assert len(post.media_urls) == 1
    assert post.platform == SocialPlatform.INSTAGRAM

def test_quality_check():
    qc = QualityCheck(
        passed=True, 
        status=QualityStatus.PASS, 
        score=95.5, 
        errors=[], 
        warnings=[], 
        improvements=["Could use more hashtags."]
    )
    assert qc.status == QualityStatus.PASS
    assert qc.passed is True
    
def test_approval_request():
    req = ApprovalRequest(
        draft_id=uuid.uuid4(),
        topic="Test",
        linkedin_content="Test LI",
        instagram_content="Test IG",
        quality_score=95.0,
    )
    assert req.status == ApprovalStatus.PENDING
    assert req.generated_timestamp is not None

def test_invalid_platform_names():
    with pytest.raises(ValidationError):
        LinkedInPost(platform="twitter", text="Hello")

def test_invalid_content_states():
    with pytest.raises(ValidationError):
        ContentDraft(
            title="AI Automation",
            hook="Hook exceeding ten chars",
            linkedin_post="This is a sufficiently long LinkedIn post containing enough characters.",
            instagram_caption="This is a sufficiently long Instagram caption containing enough characters.",
            cta="Call to action",
            hashtags=["ai"],
            state="archived"
        )

import pytest
import uuid
import httpx
from unittest.mock import AsyncMock, patch
from initials_agent.models.workflow import ApprovalRequest, ApprovalStatus
from initials_agent.services.publishing.linkedin import LinkedInPublisher
from initials_agent.services.publishing.instagram import InstagramPublisher
from initials_agent.services.publishing.service import PublishingService
from initials_agent.repositories.publishing import PublishingRepository
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from initials_agent.db.models import Base

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    s = Session()
    yield s
    s.close()

@pytest.fixture
def req():
    return ApprovalRequest(
        id=uuid.uuid4(),
        draft_id=uuid.uuid4(),
        topic="Test",
        linkedin_content="LI Post",
        instagram_content="IG Post",
        image_path="http://example.com/image.jpg",
        quality_score=95,
        status=ApprovalStatus.APPROVED
    )

@pytest.mark.asyncio
async def test_publishing_service_success(session, req):
    repo = PublishingRepository(session)
    li_pub = LinkedInPublisher("token", "urn")
    ig_pub = InstagramPublisher("token", "ig_id")
    
    # Mock httpx clients
    mock_li_post = AsyncMock()
    mock_li_post.return_value.raise_for_status = lambda: None
    mock_li_post.return_value.headers = {"x-restli-id": "real-li-id"}
    li_pub.client.post = mock_li_post
    
    mock_ig_post = AsyncMock()
    mock_ig_post.return_value.raise_for_status = lambda: None
    mock_ig_post.return_value.json = lambda: {"id": "real-ig-id"}
    ig_pub.client.post = mock_ig_post
    
    service = PublishingService(li_pub, ig_pub, repo)
    results = await service.publish_approved_request(req)
    
    assert results["linkedin"] == "real-li-id"
    assert results["instagram"] == "real-ig-id"
    
    # Ensure idempotency rejection
    with pytest.raises(ValueError, match="already been published"):
        await service.publish_approved_request(req)
        
@pytest.mark.asyncio
async def test_publishing_service_requires_approval(session, req):
    req.status = ApprovalStatus.PENDING
    repo = PublishingRepository(session)
    service = PublishingService(None, None, repo)
    
    with pytest.raises(ValueError, match="Must be APPROVED"):
        await service.publish_approved_request(req)

@pytest.mark.asyncio
async def test_publishing_linkedin_retry_failure(req):
    from tenacity import RetryError
    li_pub = LinkedInPublisher("token", "urn")
    
    class FakeResponse:
        status_code = 500
        text = "Server Error"
    
    def raise_err(*args, **kwargs):
        raise httpx.HTTPStatusError("500", request=None, response=FakeResponse())
        
    mock_post = AsyncMock(side_effect=raise_err)
    li_pub.client.post = mock_post
    
    with pytest.raises(RetryError):
        await li_pub.publish(req)
    
    # Should retry 3 times based on tenacity configuration
    assert mock_post.call_count == 3

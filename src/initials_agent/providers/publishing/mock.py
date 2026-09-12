import uuid

from initials_agent.models.workflow import ApprovalRequest
from initials_agent.services.publishing.base import SocialPublisher


class MockSocialPublisher(SocialPublisher):
    async def validate_media(self, media_path: str) -> bool:
        return True
        
    async def publish(self, request: ApprovalRequest) -> str:
        return f"mock-{uuid.uuid4()}"
        
    async def get_status(self, external_id: str) -> str:
        return "PUBLISHED"

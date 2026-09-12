from abc import ABC, abstractmethod

from initials_agent.models.workflow import ApprovalRequest


class SocialPublisher(ABC):
    @abstractmethod
    async def publish(self, request: ApprovalRequest) -> str:
        """Publishes the approved request and returns the external post ID."""
        
    @abstractmethod
    async def validate_media(self, media_path: str) -> bool:
        """Validates if the media is supported by the platform."""
        
    @abstractmethod
    async def get_status(self, external_id: str) -> str:
        """Returns the status of the post."""

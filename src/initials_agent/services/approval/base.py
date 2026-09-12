import uuid
from abc import ABC, abstractmethod

from initials_agent.models.workflow import ApprovalRequest


class ApprovalService(ABC):
    @abstractmethod
    def list_pending(self) -> list[ApprovalRequest]:
        """List all pending approval requests."""
        
    @abstractmethod
    def get_request(self, request_id: uuid.UUID) -> ApprovalRequest | None:
        """Get a specific approval request."""
        
    @abstractmethod
    def approve(self, request_id: uuid.UUID) -> None:
        """Approve a request."""
        
    @abstractmethod
    def reject(self, request_id: uuid.UUID, reason: str = None) -> None:
        """Reject a request."""
        
    @abstractmethod
    def regenerate(self, request_id: uuid.UUID, instructions: str = None) -> None:
        """Request regeneration for a draft."""

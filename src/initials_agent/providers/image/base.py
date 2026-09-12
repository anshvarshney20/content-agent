from abc import ABC, abstractmethod

from initials_agent.models.content import VisualConcept


class ImageProvider(ABC):
    @abstractmethod
    async def generate_image(self, concept: VisualConcept) -> bytes:
        """Generate an image based on the provided VisualConcept and return raw bytes."""

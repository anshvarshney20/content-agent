import io

from PIL import Image

from initials_agent.models.content import VisualConcept

from .base import ImageProvider


class MockImageProvider(ImageProvider):
    async def generate_image(self, concept: VisualConcept) -> bytes:
        img = Image.new("RGB", (150, 150), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

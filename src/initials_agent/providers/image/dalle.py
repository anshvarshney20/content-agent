import base64

from initials_agent.models.content import VisualConcept
from initials_agent.providers.image.http_util import ImageProviderError, post_json_with_retry

from .base import ImageProvider


class DalleImageProvider(ImageProvider):
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key is required for DalleImageProvider")
        self.api_key = api_key

    async def generate_image(self, concept: VisualConcept) -> bytes:
        prompt = concept.visual_subject
        if concept.headline and concept.headline != "CLI Prompt":
            prompt = (
                f"Headline: {concept.headline}\nSubject: {concept.visual_subject}\n"
                f"Style: {concept.composition}, {concept.environment}, {concept.lighting}"
            )

        response = await post_json_with_retry(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024",
                "response_format": "b64_json",
            },
            provider_name="DALL-E",
            on_retry=getattr(self, "on_retry", None),
        )
        data = response.json()
        try:
            return base64.b64decode(data["data"][0]["b64_json"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ImageProviderError(f"Unexpected response format from DALL-E API: {data}") from exc

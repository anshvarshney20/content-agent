import base64

from initials_agent.models.content import VisualConcept
from initials_agent.providers.image.http_util import ImageProviderError, post_json_with_retry

from .base import ImageProvider

OPENROUTER_IMAGES_URL = "https://openrouter.ai/api/v1/images"
DEFAULT_MODEL = "bytedance-seed/seedream-4.5"


def map_aspect_ratio(raw: str | None) -> str:
    """Normalize VisualConcept aspect ratios to OpenRouter-friendly values."""
    value = (raw or "1:1").strip().lower()
    # Pixel sizes from VisualContentService → ratio strings
    pixel_map = {
        "1080x1350": "3:4",
        "1080x1920": "9:16",
        "1200x1200": "1:1",
        "1200x1350": "4:5",
        "1024x1024": "1:1",
    }
    if value in pixel_map:
        return pixel_map[value]
    if "x" in value and ":" not in value:
        try:
            w, h = value.split("x", 1)
            wi, hi = int(w), int(h)
            if wi == hi:
                return "1:1"
            if abs(wi / hi - 4 / 5) < 0.05:
                return "4:5"
            if abs(wi / hi - 3 / 4) < 0.05:
                return "3:4"
            if abs(wi / hi - 16 / 9) < 0.05:
                return "16:9"
            if abs(wi / hi - 9 / 16) < 0.05:
                return "9:16"
        except ValueError:
            pass
    if value == "4:5":
        return "4:5"
    if value in {"1:1", "3:4", "4:3", "16:9", "9:16"}:
        return value
    return "1:1"


class OpenRouterImageProvider(ImageProvider):
    def __init__(self, api_key: str, model_name: str = DEFAULT_MODEL):
        if not api_key:
            raise ValueError("API key is required for OpenRouterImageProvider")
        self.api_key = api_key
        self.model_name = model_name or DEFAULT_MODEL

    async def generate_image(self, concept: VisualConcept) -> bytes:
        prompt = concept.visual_subject
        if concept.headline and concept.headline != "CLI Prompt":
            prompt = (
                f"Headline: {concept.headline}\nSubject: {concept.visual_subject}\n"
                f"Style: {concept.composition}, {concept.environment}, {concept.lighting}"
            )

        aspect_ratio = map_aspect_ratio(concept.aspect_ratio)
        response = await post_json_with_retry(
            OPENROUTER_IMAGES_URL,
            headers={
                "Authorization": f"Bearer {self.api_key.strip()}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/initials-agent",
                "X-Title": "Daily Content Agent",
            },
            json={
                "model": self.model_name,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
            },
            provider_name="OpenRouter",
            timeout=120.0,
            on_retry=getattr(self, "on_retry", None),
        )
        data = response.json()
        try:
            b64_data = data["data"][0]["b64_json"]
            # Some providers return a data URL prefix
            if isinstance(b64_data, str) and "," in b64_data and b64_data.startswith("data:"):
                b64_data = b64_data.split(",", 1)[1]
            return base64.b64decode(b64_data)
        except (KeyError, IndexError, TypeError) as exc:
            raise ImageProviderError(f"Unexpected response format from OpenRouter API: {data}") from exc

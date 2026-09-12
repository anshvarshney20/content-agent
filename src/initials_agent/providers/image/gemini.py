import base64

from initials_agent.models.content import VisualConcept
from initials_agent.providers.image.http_util import ImageProviderError, post_json_with_retry

from .base import ImageProvider

# Imagen predict models are retired on the Gemini Developer API.
# Use Gemini native image generation instead.
DEFAULT_GEMINI_IMAGE_MODEL = "gemini-2.5-flash-image"
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def resolve_gemini_image_model(model_name: str | None) -> str:
    """Map retired Imagen IDs to a working Gemini image model."""
    raw = (model_name or DEFAULT_GEMINI_IMAGE_MODEL).strip()
    lower = raw.lower()
    if lower.startswith("imagen-") or lower.startswith("bytedance-") or "/" in lower:
        return DEFAULT_GEMINI_IMAGE_MODEL
    return raw or DEFAULT_GEMINI_IMAGE_MODEL


def map_imagen_aspect_ratio(raw: str | None) -> str:
    value = (raw or "1:1").strip().lower()
    pixel_map = {
        "1080x1350": "3:4",
        "1080x1920": "9:16",
        "1200x1200": "1:1",
        "1200x1350": "3:4",
        "1024x1024": "1:1",
    }
    if value in pixel_map:
        return pixel_map[value]
    if value == "4:5":
        return "3:4"
    if value in {"1:1", "3:4", "4:3", "9:16", "16:9"}:
        return value
    return "1:1"


def _extract_inline_b64(data: dict) -> str:
    """Pull base64 image bytes from a generateContent response."""
    candidates = data.get("candidates") or []
    for cand in candidates:
        parts = ((cand.get("content") or {}).get("parts")) or []
        for part in parts:
            inline = part.get("inlineData") or part.get("inline_data") or {}
            b64 = inline.get("data")
            if b64:
                return b64
    raise KeyError("no inline image data")


class GeminiImageProvider(ImageProvider):
    """Google Gemini native image generation (generateContent)."""

    def __init__(self, api_key: str, model_name: str = DEFAULT_GEMINI_IMAGE_MODEL):
        if not api_key:
            raise ValueError("API key is required for GeminiImageProvider")
        self.api_key = api_key
        self.model_name = resolve_gemini_image_model(model_name)

    async def generate_image(self, concept: VisualConcept) -> bytes:
        prompt = concept.visual_subject
        if concept.headline and concept.headline != "CLI Prompt":
            prompt = (
                f"Headline: {concept.headline}\nSubject: {concept.visual_subject}\n"
                f"Style: {concept.composition}, {concept.environment}, {concept.lighting}"
            )

        aspect_ratio = map_imagen_aspect_ratio(concept.aspect_ratio)
        url = f"{GEMINI_API_BASE}/{self.model_name}:generateContent"
        response = await post_json_with_retry(
            url,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key.strip(),
            },
            json={
                "contents": [
                    {
                        "role": "user",
                        "parts": [
                            {
                                "text": (
                                    f"Generate a high-quality marketing image. "
                                    f"Aspect ratio {aspect_ratio}. {prompt}"
                                )
                            }
                        ],
                    }
                ],
                "generationConfig": {
                    "responseModalities": ["TEXT", "IMAGE"],
                    "imageConfig": {"aspectRatio": aspect_ratio},
                },
            },
            provider_name="Gemini",
            timeout=120.0,
            on_retry=getattr(self, "on_retry", None),
        )
        data = response.json()
        try:
            b64_data = _extract_inline_b64(data)
            return base64.b64decode(b64_data)
        except (KeyError, IndexError, TypeError) as exc:
            raise ImageProviderError(
                "Gemini returned no image. "
                f"Model={self.model_name}. Response: {str(data)[:240]}"
            ) from exc

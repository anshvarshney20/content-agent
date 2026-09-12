import base64
from unittest.mock import MagicMock

import pytest

from initials_agent.models.content import VisualConcept
from initials_agent.providers.image.gemini import (
    DEFAULT_GEMINI_IMAGE_MODEL,
    GeminiImageProvider,
    map_imagen_aspect_ratio,
    resolve_gemini_image_model,
)
from initials_agent.providers.image.http_util import ImageProviderError


def _concept(**kwargs) -> VisualConcept:
    base = dict(
        aspect_ratio="4:5",
        composition="minimal",
        headline="CLI Prompt",
        supporting_text="",
        visual_subject="Premium enterprise AI visual",
        environment="studio",
        lighting="cinematic",
        color_palette="dark",
        typography="none",
        negative_prompt="",
        brand_requirements="INITΛLS",
    )
    base.update(kwargs)
    return VisualConcept(**base)


def test_map_imagen_aspect_ratio():
    assert map_imagen_aspect_ratio("4:5") == "3:4"
    assert map_imagen_aspect_ratio("1:1") == "1:1"
    assert map_imagen_aspect_ratio("1080x1350") == "3:4"


def test_resolve_maps_retired_imagen():
    assert resolve_gemini_image_model("imagen-3.0-generate-002") == DEFAULT_GEMINI_IMAGE_MODEL
    assert resolve_gemini_image_model("imagen-4.0-generate-001") == DEFAULT_GEMINI_IMAGE_MODEL
    assert resolve_gemini_image_model("gemini-2.5-flash-image") == "gemini-2.5-flash-image"


@pytest.mark.asyncio
async def test_flash_image_generate_content(monkeypatch):
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"flash"
    b64 = base64.b64encode(png_bytes).decode()
    captured = {}

    async def fake_post(url, *, headers, json, provider_name, timeout=90.0, max_attempts=4, on_retry=None):
        captured["url"] = url
        captured["json"] = json
        assert provider_name == "Gemini"
        resp = MagicMock()
        resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"inlineData": {"data": b64}}]}}]
        }
        return resp

    monkeypatch.setattr(
        "initials_agent.providers.image.gemini.post_json_with_retry",
        fake_post,
    )
    provider = GeminiImageProvider("test-key", "imagen-3.0-generate-002")
    assert provider.model_name == "gemini-2.5-flash-image"
    out = await provider.generate_image(_concept())
    assert out == png_bytes
    assert captured["url"].endswith("gemini-2.5-flash-image:generateContent")
    assert "IMAGE" in captured["json"]["generationConfig"]["responseModalities"]


@pytest.mark.asyncio
async def test_missing_image_friendly_error(monkeypatch):
    async def fake_post(*args, **kwargs):
        resp = MagicMock()
        resp.json.return_value = {"candidates": [{"content": {"parts": [{"text": "nope"}]}}]}
        return resp

    monkeypatch.setattr(
        "initials_agent.providers.image.gemini.post_json_with_retry",
        fake_post,
    )
    provider = GeminiImageProvider("test-key")
    with pytest.raises(ImageProviderError, match="no image"):
        await provider.generate_image(_concept())


def test_build_image_provider_gemini(monkeypatch):
    from initials_agent.config import ImageGenerationConfig, Settings
    from initials_agent import runtime

    def mock_settings():
        s = Settings()
        s.image = ImageGenerationConfig(
            provider="gemini",
            api_key="test-key",
            model_name="imagen-3.0-generate-002",
        )
        return s

    monkeypatch.setattr(runtime, "get_settings", mock_settings)
    prov = runtime.build_image_provider()
    assert isinstance(prov, GeminiImageProvider)
    assert prov.model_name == "gemini-2.5-flash-image"

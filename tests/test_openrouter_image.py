import base64
from unittest.mock import AsyncMock, MagicMock

import pytest

from initials_agent.models.content import VisualConcept
from initials_agent.providers.image.http_util import ImageProviderError
from initials_agent.providers.image.openrouter import (
    OPENROUTER_IMAGES_URL,
    OpenRouterImageProvider,
    map_aspect_ratio,
)


def _concept(**kwargs) -> VisualConcept:
    base = dict(
        aspect_ratio="4:5",
        composition="minimal",
        headline="CLI Prompt",
        supporting_text="",
        visual_subject="Premium AI agent workflow visual",
        environment="studio",
        lighting="cinematic",
        color_palette="dark",
        typography="none",
        negative_prompt="",
        brand_requirements="INITΛLS",
    )
    base.update(kwargs)
    return VisualConcept(**base)


def test_map_aspect_ratio():
    assert map_aspect_ratio("4:5") == "4:5"
    assert map_aspect_ratio("1080x1350") == "3:4"
    assert map_aspect_ratio("1200x1200") == "1:1"
    assert map_aspect_ratio(None) == "1:1"


@pytest.mark.asyncio
async def test_openrouter_success(monkeypatch):
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"fake"
    b64 = base64.b64encode(png_bytes).decode()
    captured = {}

    async def fake_post(url, *, headers, json, provider_name, timeout=90.0, max_attempts=4, on_retry=None):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["provider_name"] = provider_name
        resp = MagicMock()
        resp.json.return_value = {"data": [{"b64_json": b64}]}
        return resp

    monkeypatch.setattr(
        "initials_agent.providers.image.openrouter.post_json_with_retry",
        fake_post,
    )

    provider = OpenRouterImageProvider("sk-or-test", "bytedance-seed/seedream-4.5")
    out = await provider.generate_image(_concept())
    assert out == png_bytes
    assert captured["url"] == OPENROUTER_IMAGES_URL
    assert captured["headers"]["Authorization"] == "Bearer sk-or-test"
    assert captured["json"]["model"] == "bytedance-seed/seedream-4.5"
    assert captured["json"]["aspect_ratio"] == "4:5"
    assert captured["provider_name"] == "OpenRouter"


@pytest.mark.asyncio
async def test_openrouter_429_friendly(monkeypatch):
    async def fake_post(*args, **kwargs):
        raise ImageProviderError("OpenRouter rate limit reached. Wait about a minute, then retry.")

    monkeypatch.setattr(
        "initials_agent.providers.image.openrouter.post_json_with_retry",
        fake_post,
    )
    provider = OpenRouterImageProvider("sk-or-test")
    with pytest.raises(ImageProviderError, match="rate limit"):
        await provider.generate_image(_concept())


@pytest.mark.asyncio
async def test_openrouter_bad_payload(monkeypatch):
    async def fake_post(*args, **kwargs):
        resp = MagicMock()
        resp.json.return_value = {"data": []}
        return resp

    monkeypatch.setattr(
        "initials_agent.providers.image.openrouter.post_json_with_retry",
        fake_post,
    )
    provider = OpenRouterImageProvider("sk-or-test")
    with pytest.raises(ImageProviderError, match="Unexpected response"):
        await provider.generate_image(_concept())


def test_build_image_provider_openrouter(monkeypatch):
    from initials_agent.config import ImageGenerationConfig, Settings
    from initials_agent.providers.image.openrouter import OpenRouterImageProvider
    from initials_agent import runtime

    def mock_settings():
        s = Settings()
        s.image = ImageGenerationConfig(
            provider="openrouter",
            api_key="sk-or-test",
            model_name="google/gemini-2.5-flash-image",
        )
        return s

    monkeypatch.setattr(runtime, "get_settings", mock_settings)
    prov = runtime.build_image_provider()
    assert isinstance(prov, OpenRouterImageProvider)
    assert prov.model_name == "google/gemini-2.5-flash-image"

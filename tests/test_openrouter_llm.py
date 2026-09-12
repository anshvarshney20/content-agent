from unittest.mock import MagicMock

import pytest

from initials_agent.models.content import ContentDraft
from initials_agent.providers.llm.openrouter import (
    DEFAULT_MODEL,
    OPENROUTER_CHAT_URL,
    OpenRouterLLMProvider,
)


@pytest.mark.asyncio
async def test_openrouter_llm_generate_json(monkeypatch):
    payload = {
        "title": "AI Agents Hit Enterprise",
        "hook": "This is a strong hook for the post.",
        "linkedin_post": "A" * 60,
        "instagram_caption": "B" * 60,
        "cta": "Comment brief for the takeaway.",
        "hashtags": ["AI", "Automation"],
        "source_references": ["https://example.com/story"],
    }

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": __import__("json").dumps(payload)}}]}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, headers=None, json=None):
            assert url == OPENROUTER_CHAT_URL
            assert headers["Authorization"] == "Bearer sk-or-test"
            assert json["model"] == DEFAULT_MODEL
            return FakeResponse()

    monkeypatch.setattr(
        "initials_agent.providers.llm.openrouter.httpx.AsyncClient",
        FakeClient,
    )

    llm = OpenRouterLLMProvider("sk-or-test", DEFAULT_MODEL)
    draft = await llm.generate_json("Write a post", "You are a writer", ContentDraft)
    assert draft.title.startswith("AI Agents")
    assert len(draft.linkedin_post) >= 50


def test_build_llm_openrouter_deepseek(monkeypatch):
    from initials_agent.config import AIProviderConfig, Settings
    from initials_agent import runtime

    def mock_settings():
        s = Settings()
        s.ai = AIProviderConfig(
            provider="openrouter",
            api_key="sk-or-test",
            model_name="deepseek/deepseek-v4-flash-0731",
        )
        return s

    monkeypatch.setattr(runtime, "get_settings", mock_settings)
    llm = runtime.build_llm()
    assert isinstance(llm, OpenRouterLLMProvider)
    assert llm.model_name == "deepseek/deepseek-v4-flash-0731"

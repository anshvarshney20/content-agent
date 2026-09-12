import pytest

from initials_agent.providers.research.rss import parse_feed
from initials_agent.runtime import build_llm


SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Tech</title>
    <item>
      <title>Open-source AI agents hit enterprise workflows</title>
      <link>https://techcrunch.com/ai-agents</link>
      <description>Companies are piloting agents for support and ops.</description>
      <pubDate>Mon, 07 Sep 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


def test_parse_rss_feed():
    items = parse_feed(SAMPLE_RSS, "techcrunch.com")
    assert len(items) == 1
    assert "AI agents" in items[0].title
    assert "techcrunch.com" in items[0].source_domain


def test_build_llm_requires_api_key(monkeypatch):
    from initials_agent.config import Settings, AIProviderConfig, ImageGenerationConfig

    monkeypatch.setattr(
        "initials_agent.runtime.get_settings",
        lambda: Settings(
            ai=AIProviderConfig(
                provider="openrouter",
                api_key=None,
                model_name="deepseek/deepseek-v4-flash-0731",
            ),
            image=ImageGenerationConfig(provider="mock", api_key=None),
        ),
    )
    with pytest.raises(RuntimeError, match="AI API key required"):
        build_llm()

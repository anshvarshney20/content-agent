import pytest

from initials_agent.providers.image.http_util import (
    ImageProviderError,
    format_http_error,
    post_json_with_retry,
    retry_after_seconds,
)


class FakeResponse:
    def __init__(self, status_code: int, headers=None, text="", json_data=None):
        self.status_code = status_code
        self.headers = headers or {}
        self.text = text
        self._json = json_data or {}
        self.is_success = 200 <= status_code < 300

    def json(self):
        return self._json


def test_format_429_is_user_friendly():
    err = format_http_error(FakeResponse(429, text="Too Many Requests"), "Gemini")
    assert isinstance(err, ImageProviderError)
    assert "rate limit" in str(err).lower()
    assert "429 Too Many Requests" not in str(err)
    assert "mozilla.org" not in str(err)


def test_retry_after_header():
    response = FakeResponse(429, headers={"Retry-After": "12"})
    assert retry_after_seconds(response, 5.0) == 12.0


@pytest.mark.asyncio
async def test_retries_429_then_succeeds(monkeypatch):
    calls = {"n": 0}
    sleeps = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, headers=None, json=None):
            calls["n"] += 1
            if calls["n"] == 1:
                return FakeResponse(429, headers={"Retry-After": "1"})
            return FakeResponse(200, json_data={"ok": True})

    async def instant_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(
        "initials_agent.providers.image.http_util.httpx.AsyncClient",
        lambda timeout=90.0: FakeClient(),
    )
    monkeypatch.setattr("initials_agent.providers.image.http_util.asyncio.sleep", instant_sleep)

    retries = []
    response = await post_json_with_retry(
        "https://example.test",
        headers={},
        json={},
        provider_name="Gemini",
        on_retry=lambda attempt, wait: retries.append((attempt, wait)),
    )
    assert response.status_code == 200
    assert calls["n"] == 2
    assert retries == [(1, 1)]
    assert sleeps == [1.0]


@pytest.mark.asyncio
async def test_exhausted_429_raises_friendly_error(monkeypatch):
    class AlwaysLimited:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, headers=None, json=None):
            return FakeResponse(429, text="quota")

    async def instant_sleep(seconds):
        return None

    monkeypatch.setattr(
        "initials_agent.providers.image.http_util.httpx.AsyncClient",
        lambda timeout=90.0: AlwaysLimited(),
    )
    monkeypatch.setattr("initials_agent.providers.image.http_util.asyncio.sleep", instant_sleep)

    with pytest.raises(ImageProviderError, match="rate limit"):
        await post_json_with_retry(
            "https://example.test",
            headers={},
            json={},
            provider_name="Gemini",
            max_attempts=2,
        )

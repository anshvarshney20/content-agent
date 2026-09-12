import asyncio
from typing import Any, Callable

import httpx

RETRYABLE_STATUS = {429, 500, 502, 503}

OnRetry = Callable[[int, int], None]


class ImageProviderError(Exception):
    """User-facing image provider failure."""


def retry_after_seconds(response: httpx.Response, fallback: float) -> float:
    header = response.headers.get("Retry-After")
    if not header:
        return fallback
    try:
        return max(1.0, float(header))
    except ValueError:
        return fallback


def format_http_error(response: httpx.Response, provider: str) -> ImageProviderError:
    status = response.status_code
    if status == 429:
        return ImageProviderError(
            f"{provider} rate limit reached. Wait about a minute, then retry."
        )
    if status in (401, 403):
        return ImageProviderError(f"{provider} rejected the API key (HTTP {status}).")
    snippet = (response.text or "").strip().replace("\n", " ")[:180]
    detail = f": {snippet}" if snippet else ""
    return ImageProviderError(f"{provider} request failed (HTTP {status}){detail}")


async def post_json_with_retry(
    url: str,
    *,
    headers: dict[str, str],
    json: dict[str, Any],
    provider_name: str,
    timeout: float = 90.0,
    max_attempts: int = 4,
    on_retry: OnRetry | None = None,
) -> httpx.Response:
    delays = (5.0, 15.0, 30.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        for attempt in range(max_attempts):
            response = await client.post(url, headers=headers, json=json)
            if response.is_success:
                return response
            retryable = response.status_code in RETRYABLE_STATUS and attempt < max_attempts - 1
            if retryable:
                wait = retry_after_seconds(response, delays[min(attempt, len(delays) - 1)])
                if on_retry:
                    on_retry(attempt + 1, int(wait))
                await asyncio.sleep(wait)
                continue
            raise format_http_error(response, provider_name)
    raise ImageProviderError(f"{provider_name} request failed after {max_attempts} attempts.")

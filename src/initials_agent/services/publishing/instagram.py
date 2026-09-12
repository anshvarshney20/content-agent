import asyncio
import logging
import os
from pathlib import Path

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from initials_agent.config import get_settings
from initials_agent.models.workflow import ApprovalRequest

from .base import SocialPublisher

logger = logging.getLogger(__name__)


def resolve_public_image_url(image_path: str) -> str:
    """Instagram Graph API needs a publicly reachable HTTPS image URL."""
    raw = (image_path or "").strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        # Localhost is not reachable by Meta
        if "127.0.0.1" in raw or "localhost" in raw:
            raise ValueError(
                "Instagram cannot fetch localhost images. Set a public HTTPS base URL "
                "in Settings (e.g. ngrok) that serves /images/."
            )
        return raw

    from initials_agent.tenant import cred_get, current_user_id

    settings = get_settings()
    if current_user_id() and current_user_id() != "local":
        base = cred_get("public_base_url") or (settings.app.public_base_url or "")
    else:
        base = (settings.app.public_base_url or "")
    base = base.strip().rstrip("/")
    if not base:
        raise ValueError(
            "Instagram posting needs a public HTTPS base URL in Settings "
            "that exposes /images/<file>. Example: https://abc123.ngrok-free.app"
        )
    if not base.startswith("https://"):
        raise ValueError("Public base URL must be HTTPS for Instagram.")

    name = os.path.basename(raw.replace("\\", "/"))
    local = Path(raw)
    if not local.exists():
        candidate = Path(os.getcwd()) / "output" / "images" / name
        if not candidate.exists():
            raise FileNotFoundError(f"Image file not found for Instagram: {raw}")
    # Prefer path relative to /images if under output/images
    try:
        rel = local.resolve().relative_to((Path.cwd() / "output" / "images").resolve())
        return f"{base}/images/{rel.as_posix()}"
    except Exception:
        return f"{base}/images/{name}"


def _graph_host(access_token: str) -> str:
    """Instagram Login tokens (IGAA…) use graph.instagram.com; Page tokens use facebook."""
    token = (access_token or "").strip()
    if token.startswith("IGAA") or token.startswith("IGAT"):
        return "https://graph.instagram.com"
    return "https://graph.facebook.com"


def _media_paths(request: ApprovalRequest) -> list[str]:
    paths = [p for p in (request.image_paths or []) if (p or "").strip()]
    if paths:
        return paths
    if request.image_path:
        return [str(request.image_path)]
    return []


class InstagramPublisher(SocialPublisher):
    def __init__(self, access_token: str, ig_user_id: str):
        if not access_token or not ig_user_id:
            raise ValueError("Instagram access token and account id are required")
        self.access_token = access_token.strip()
        self.ig_user_id = ig_user_id.strip()
        self.api_host = _graph_host(self.access_token)
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(60.0))
        logger.info("Instagram publisher using %s", self.api_host)

    async def validate_media(self, media_path: str) -> bool:
        return bool(media_path)

    async def _wait_for_container(self, container_id: str) -> None:
        status_url = f"{self.api_host}/v19.0/{container_id}"
        for _ in range(20):
            resp = await self.client.get(
                status_url,
                params={"fields": "status_code", "access_token": self.access_token},
            )
            if resp.is_error:
                raise RuntimeError(f"Instagram container status failed: {resp.text}")
            code = (resp.json() or {}).get("status_code")
            if code == "FINISHED":
                return
            if code == "ERROR":
                raise RuntimeError(f"Instagram media container failed: {resp.json()}")
            await asyncio.sleep(2)
        logger.warning(
            "Instagram container %s not FINISHED yet; attempting publish anyway",
            container_id,
        )

    def _location_params(self) -> dict:
        from initials_agent.tenant import cred_get, current_user_id

        settings = get_settings()
        if current_user_id() and current_user_id() != "local":
            location_id = cred_get("instagram_location_id")
            location_name = cred_get("instagram_location_name")
        else:
            location_id = (settings.instagram.location_id or "").strip()
            location_name = settings.instagram.location_name or ""
        if not location_id:
            return {}
        logger.info(
            "Tagging Instagram post with location_id=%s (%s)",
            location_id,
            location_name,
        )
        return {"location_id": location_id}

    async def _create_item_container(self, image_url: str, *, carousel_item: bool) -> str:
        container_url = f"{self.api_host}/v19.0/{self.ig_user_id}/media"
        params = {
            "image_url": image_url,
            "access_token": self.access_token,
        }
        if carousel_item:
            params["is_carousel_item"] = "true"
        resp = await self.client.post(container_url, params=params)
        if resp.is_error:
            raise RuntimeError(f"Instagram item container failed: {resp.text}")
        container_id = (resp.json() or {}).get("id")
        if not container_id:
            raise RuntimeError(f"Instagram item container failed: {resp.text}")
        await self._wait_for_container(container_id)
        return container_id

    async def _publish_single(self, image_url: str, caption: str) -> str:
        container_url = f"{self.api_host}/v19.0/{self.ig_user_id}/media"
        params = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.access_token,
            **self._location_params(),
        }
        resp = await self.client.post(container_url, params=params)
        if resp.is_error:
            raise RuntimeError(f"Instagram container create failed: {resp.text}")
        container_id = (resp.json() or {}).get("id")
        if not container_id:
            raise RuntimeError(f"Instagram container create failed: {resp.text}")
        await self._wait_for_container(container_id)
        return await self._media_publish(container_id)

    async def _publish_carousel(self, image_urls: list[str], caption: str) -> str:
        # Meta: 2–10 children; create item containers then parent CAROUSEL
        urls = image_urls[:10]
        if len(urls) < 2:
            return await self._publish_single(urls[0], caption)

        child_ids: list[str] = []
        for i, url in enumerate(urls, start=1):
            logger.info("Creating Instagram carousel item %s/%s", i, len(urls))
            child_ids.append(await self._create_item_container(url, carousel_item=True))

        container_url = f"{self.api_host}/v19.0/{self.ig_user_id}/media"
        params = {
            "media_type": "CAROUSEL",
            "children": ",".join(child_ids),
            "caption": caption,
            "access_token": self.access_token,
            **self._location_params(),
        }
        resp = await self.client.post(container_url, params=params)
        if resp.is_error:
            raise RuntimeError(f"Instagram carousel container failed: {resp.text}")
        container_id = (resp.json() or {}).get("id")
        if not container_id:
            raise RuntimeError(f"Instagram carousel container failed: {resp.text}")
        await self._wait_for_container(container_id)
        logger.info("Publishing Instagram carousel with %s slides", len(child_ids))
        return await self._media_publish(container_id)

    async def _media_publish(self, creation_id: str) -> str:
        publish_url = f"{self.api_host}/v19.0/{self.ig_user_id}/media_publish"
        pub_resp = await self.client.post(
            publish_url,
            params={"creation_id": creation_id, "access_token": self.access_token},
        )
        if pub_resp.is_error:
            raise RuntimeError(f"Instagram publish failed: {pub_resp.text}")
        return pub_resp.json().get("id", "mock-ig-id")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError,)),
    )
    async def publish(self, request: ApprovalRequest) -> str:
        paths = _media_paths(request)
        if not paths:
            raise ValueError("Instagram requires an image.")

        caption = request.instagram_content or ""
        image_urls = [resolve_public_image_url(p) for p in paths]

        if len(image_urls) >= 2:
            return await self._publish_carousel(image_urls, caption)
        return await self._publish_single(image_urls[0], caption)

    async def get_status(self, external_id: str) -> str:
        return "PUBLISHED"

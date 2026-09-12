import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from initials_agent.models.workflow import ApprovalRequest

from .base import SocialPublisher

logger = logging.getLogger(__name__)

class LinkedInPublisher(SocialPublisher):
    def __init__(self, access_token: str, author_urn: str):
        self.access_token = access_token
        self.author_urn = author_urn
        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Linkedin-Version": "202609",
                "X-Restli-Protocol-Version": "2.0.0"
            },
            timeout=httpx.Timeout(10.0)
        )
        
    async def validate_media(self, media_path: str) -> bool:
        if not media_path:
            return False
        return True
        
    @retry(
        stop=stop_after_attempt(3), 
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
    )
    async def publish(self, request: ApprovalRequest) -> str:
        payload = {
            "author": self.author_urn,
            "commentary": request.linkedin_content,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": []
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False
        }
        
        response = await self.client.post("https://api.linkedin.com/rest/posts", json=payload)
        response.raise_for_status()
        
        urn = response.headers.get("x-restli-id", "mock-linkedin-id")
        return urn

    async def get_status(self, external_id: str) -> str:
        response = await self.client.get(f"https://api.linkedin.com/rest/posts/{external_id}")
        response.raise_for_status()
        return "PUBLISHED"

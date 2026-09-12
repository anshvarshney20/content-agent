from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl

from .enums import SocialPlatform


def utc_now() -> datetime:
    return datetime.now(UTC)

class LinkedInPost(BaseModel):
    platform: SocialPlatform = SocialPlatform.LINKEDIN
    text: str = Field(..., max_length=3000)
    media_urls: list[HttpUrl] = Field(default_factory=list)

class InstagramPost(BaseModel):
    platform: SocialPlatform = SocialPlatform.INSTAGRAM
    caption: str = Field(..., max_length=2200)
    media_urls: list[HttpUrl] = Field(..., min_length=1) # Instagram requires at least one media
    hashtags: list[str] = Field(default_factory=list)

class PublishedPost(BaseModel):
    platform: SocialPlatform
    post_id: str = Field(..., min_length=1)
    url: HttpUrl
    published_at: datetime = Field(default_factory=utc_now)

class PostAnalytics(BaseModel):
    platform: SocialPlatform
    post_id: str = Field(..., min_length=1)
    likes: int = Field(default=0, ge=0)
    comments: int = Field(default=0, ge=0)
    shares: int = Field(default=0, ge=0)
    impressions: int = Field(default=0, ge=0)
    collected_at: datetime = Field(default_factory=utc_now)

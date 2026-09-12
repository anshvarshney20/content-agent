import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


def utc_now():
    return datetime.now(UTC)

class AnalyticsSnapshot(BaseModel):
    impressions: int = 0
    reach: int = 0
    likes: int = 0
    comments: int = 0
    shares: int = 0
    saves: int = 0
    clicks: int = 0
    profile_visits: int = 0
    followers_gained: int = 0
    engagement_rate: float = 0.0

class ContentStrategyProfile(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    is_active: bool = True
    strongest_topics: list[str] = Field(default_factory=list)
    weakest_topics: list[str] = Field(default_factory=list)
    strongest_formats: list[str] = Field(default_factory=list)
    best_hooks: list[str] = Field(default_factory=list)
    best_posting_times: list[str] = Field(default_factory=list)
    engagement_trends: list[str] = Field(default_factory=list)
    repeated_themes: list[str] = Field(default_factory=list)
    content_fatigue: list[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=utc_now)

from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl


def utc_now() -> datetime:
    return datetime.now(UTC)

class ResearchSource(BaseModel):
    url: HttpUrl
    title: str = Field(..., min_length=1)
    published_date: datetime | None = None
    credibility_score: float = Field(..., ge=0.0, le=1.0)
    # RSS/description blurb used by the writer for story-specific newsjacking
    snippet: str = ""

class ResearchResult(BaseModel):
    query: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=10)
    sources: list[ResearchSource] = Field(default_factory=list)
    gathered_at: datetime = Field(default_factory=utc_now)

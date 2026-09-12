import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl

from .enums import ApprovalStatus, QualityStatus


def utc_now() -> datetime:
    return datetime.now(UTC)

class QualityCheck(BaseModel):
    passed: bool
    status: QualityStatus
    score: float = Field(..., ge=0.0, le=100.0)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    checked_at: datetime = Field(default_factory=utc_now)

class ApprovalRequest(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    draft_id: uuid.UUID
    topic: str
    linkedin_content: str
    instagram_content: str
    image_path: str | None = None
    # Instagram carousel slides (ordered). image_path stays as the first slide for compat.
    image_paths: list[str] = Field(default_factory=list)
    quality_score: float
    warnings: list[str] = Field(default_factory=list)
    source_urls: list[HttpUrl] = Field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.PENDING
    reviewer_notes: str | None = None
    generated_timestamp: datetime = Field(default_factory=utc_now)
    resolved_at: datetime | None = None

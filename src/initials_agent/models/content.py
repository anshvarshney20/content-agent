from datetime import UTC, datetime

from pydantic import BaseModel, Field, HttpUrl

from .enums import ContentState


def utc_now() -> datetime:
    return datetime.now(UTC)

class Topic(BaseModel):
    title: str = Field(..., min_length=3)
    description: str = Field(..., min_length=10)
    is_approved: bool = False
    created_at: datetime = Field(default_factory=utc_now)

class VisualConcept(BaseModel):
    aspect_ratio: str
    composition: str
    headline: str
    supporting_text: str
    visual_subject: str
    environment: str
    lighting: str
    color_palette: str
    typography: str
    negative_prompt: str
    brand_requirements: str


class CarouselSlideSpec(BaseModel):
    """One swipe card in an Instagram carousel."""

    slide_index: int = Field(..., ge=1)
    role: str  # hook | insight | bridge | detail | cta
    headline: str
    supporting_text: str
    visual_subject: str
    composition: str


class InstagramCarouselPlan(BaseModel):
    """Ordered slide plan for a swipeable Instagram carousel."""

    slides: list[CarouselSlideSpec] = Field(..., min_length=2, max_length=10)

class GeneratedAsset(BaseModel):
    url: str
    asset_type: str = Field(..., min_length=1)
    created_at: datetime = Field(default_factory=utc_now)

class ContentDraft(BaseModel):
    title: str = Field(..., min_length=5)
    hook: str = Field(..., min_length=10)
    linkedin_post: str = Field(..., min_length=50)
    instagram_caption: str = Field(..., min_length=50)
    cta: str = Field(..., min_length=5)
    hashtags: list[str] = Field(..., min_length=1)
    visual_concept: VisualConcept | None = None
    assets: list[GeneratedAsset] = Field(default_factory=list)
    source_references: list[HttpUrl] = Field(default_factory=list)
    state: ContentState = ContentState.DRAFT

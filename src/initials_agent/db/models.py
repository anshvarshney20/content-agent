import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now():
    return datetime.now(UTC)

class Base(DeclarativeBase):
    pass

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, onupdate=utc_now)

class TopicModel(Base, TimestampMixin):
    __tablename__ = "topics"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(String, nullable=True)
    angle: Mapped[str | None] = mapped_column(String, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)

    sources: Mapped[list["ResearchSourceModel"]] = relationship(back_populates="topic")
    drafts: Mapped[list["ContentDraftModel"]] = relationship(back_populates="topic")

class ResearchSourceModel(Base, TimestampMixin):
    __tablename__ = "research_sources"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"))
    url: Mapped[str] = mapped_column(String, index=True)
    title: Mapped[str] = mapped_column(String)
    published_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    credibility_score: Mapped[float] = mapped_column(Float)

    topic: Mapped["TopicModel"] = relationship(back_populates="sources")

class ContentDraftModel(Base, TimestampMixin):
    __tablename__ = "content_drafts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id"))
    title: Mapped[str] = mapped_column(String)
    hook: Mapped[str] = mapped_column(String)
    linkedin_post: Mapped[str] = mapped_column(String)
    instagram_caption: Mapped[str] = mapped_column(String)
    cta: Mapped[str] = mapped_column(String)
    hashtags: Mapped[list] = mapped_column(JSON)
    source_references: Mapped[list] = mapped_column(JSON)
    state: Mapped[str] = mapped_column(String, index=True)

    topic: Mapped["TopicModel"] = relationship(back_populates="drafts")
    visual_concept: Mapped[Optional["VisualConceptModel"]] = relationship(back_populates="draft", uselist=False)
    assets: Mapped[list["GeneratedAssetModel"]] = relationship(back_populates="draft")
    quality_checks: Mapped[list["QualityCheckModel"]] = relationship(back_populates="draft")
    approval_requests: Mapped[list["ApprovalRequestModel"]] = relationship(back_populates="draft")
    published_posts: Mapped[list["PublishedPostModel"]] = relationship(back_populates="draft")

class VisualConceptModel(Base, TimestampMixin):
    __tablename__ = "visual_concepts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_drafts.id"), unique=True)
    aspect_ratio: Mapped[str] = mapped_column(String)
    composition: Mapped[str] = mapped_column(String)
    headline: Mapped[str] = mapped_column(String)
    supporting_text: Mapped[str] = mapped_column(String)
    visual_subject: Mapped[str] = mapped_column(String)
    environment: Mapped[str] = mapped_column(String)
    lighting: Mapped[str] = mapped_column(String)
    color_palette: Mapped[str] = mapped_column(String)
    typography: Mapped[str] = mapped_column(String)
    negative_prompt: Mapped[str] = mapped_column(String)
    brand_requirements: Mapped[str] = mapped_column(String)

    draft: Mapped["ContentDraftModel"] = relationship(back_populates="visual_concept")

class GeneratedAssetModel(Base, TimestampMixin):
    __tablename__ = "generated_assets"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_drafts.id"))
    url: Mapped[str] = mapped_column(String)
    asset_type: Mapped[str] = mapped_column(String)

    draft: Mapped["ContentDraftModel"] = relationship(back_populates="assets")

class StandaloneVisualModel(Base, TimestampMixin):
    __tablename__ = "standalone_visuals"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    content_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("content_drafts.id"), nullable=True)
    topic: Mapped[str] = mapped_column(String)
    prompt: Mapped[str] = mapped_column(String)
    provider: Mapped[str] = mapped_column(String)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String)
    generation_error: Mapped[str | None] = mapped_column(String, nullable=True)

class QualityCheckModel(Base, TimestampMixin):
    __tablename__ = "quality_checks"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_drafts.id"))
    passed: Mapped[bool] = mapped_column(Boolean)
    status: Mapped[str] = mapped_column(String)
    score: Mapped[float] = mapped_column(Float)
    errors: Mapped[list] = mapped_column(JSON)
    warnings: Mapped[list] = mapped_column(JSON)
    improvements: Mapped[list] = mapped_column(JSON)
    checked_at: Mapped[datetime] = mapped_column(DateTime)

    draft: Mapped["ContentDraftModel"] = relationship(back_populates="quality_checks")

class ApprovalRequestModel(Base, TimestampMixin):
    __tablename__ = "approval_requests"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_drafts.id"))
    status: Mapped[str] = mapped_column(String)
    reviewer_notes: Mapped[str | None] = mapped_column(String, nullable=True)

    draft: Mapped["ContentDraftModel"] = relationship(back_populates="approval_requests")

class PublishedPostModel(Base, TimestampMixin):
    __tablename__ = "published_posts"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    draft_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("content_drafts.id"))
    platform: Mapped[str] = mapped_column(String)
    external_id: Mapped[str] = mapped_column(String, index=True)
    url: Mapped[str] = mapped_column(String)
    published_at: Mapped[datetime] = mapped_column(DateTime)

    draft: Mapped["ContentDraftModel"] = relationship(back_populates="published_posts")
    analytics: Mapped[list["AnalyticsModel"]] = relationship(back_populates="post")

class AnalyticsModel(Base, TimestampMixin):
    __tablename__ = "analytics"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("published_posts.id"))
    impressions: Mapped[int] = mapped_column(Integer, default=0)
    reach: Mapped[int] = mapped_column(Integer, default=0)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    comments: Mapped[int] = mapped_column(Integer, default=0)
    shares: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    clicks: Mapped[int] = mapped_column(Integer, default=0)
    profile_visits: Mapped[int] = mapped_column(Integer, default=0)
    followers_gained: Mapped[int] = mapped_column(Integer, default=0)
    engagement_rate: Mapped[float] = mapped_column(Float, default=0.0)
    recorded_at: Mapped[datetime] = mapped_column(DateTime)

    post: Mapped["PublishedPostModel"] = relationship(back_populates="analytics")

class ContentStrategyProfileModel(Base, TimestampMixin):
    __tablename__ = "content_strategy_profiles"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    strongest_topics: Mapped[list] = mapped_column(JSON, default=list)
    weakest_topics: Mapped[list] = mapped_column(JSON, default=list)
    strongest_formats: Mapped[list] = mapped_column(JSON, default=list)
    best_hooks: Mapped[list] = mapped_column(JSON, default=list)
    best_posting_times: Mapped[list] = mapped_column(JSON, default=list)
    engagement_trends: Mapped[list] = mapped_column(JSON, default=list)
    repeated_themes: Mapped[list] = mapped_column(JSON, default=list)
    content_fatigue: Mapped[list] = mapped_column(JSON, default=list)
    last_updated: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

class PipelineRunModel(Base, TimestampMixin):
    __tablename__ = "pipeline_runs"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_date: Mapped[str] = mapped_column(String, index=True, unique=True) # e.g. '2026-09-06'
    status: Mapped[str] = mapped_column(String) # 'running', 'success', 'failed'
    logs: Mapped[str | None] = mapped_column(String, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)


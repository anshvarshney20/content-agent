import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from initials_agent.db.models import (
    AnalyticsModel,
    ContentStrategyProfileModel,
    PublishedPostModel,
)
from initials_agent.models.analytics import AnalyticsSnapshot, ContentStrategyProfile


class AnalyticsRepository:
    def __init__(self, session: Session):
        self.session = session
        
    def get_published_posts(self) -> list[PublishedPostModel]:
        return self.session.query(PublishedPostModel).all()
        
    def save_snapshot(self, post_id: uuid.UUID, snapshot: AnalyticsSnapshot) -> AnalyticsModel:
        model = AnalyticsModel(
            post_id=post_id,
            impressions=snapshot.impressions,
            reach=snapshot.reach,
            likes=snapshot.likes,
            comments=snapshot.comments,
            shares=snapshot.shares,
            saves=snapshot.saves,
            clicks=snapshot.clicks,
            profile_visits=snapshot.profile_visits,
            followers_gained=snapshot.followers_gained,
            engagement_rate=snapshot.engagement_rate,
            recorded_at=datetime.now(UTC)
        )
        self.session.add(model)
        self.session.commit()
        return model

    def get_latest_profile(self) -> ContentStrategyProfileModel:
        return self.session.query(ContentStrategyProfileModel).filter_by(is_active=True).order_by(ContentStrategyProfileModel.created_at.desc()).first()

    def save_profile(self, profile: ContentStrategyProfile) -> ContentStrategyProfileModel:
        model = ContentStrategyProfileModel(
            id=profile.id,
            is_active=profile.is_active,
            strongest_topics=profile.strongest_topics,
            weakest_topics=profile.weakest_topics,
            strongest_formats=profile.strongest_formats,
            best_hooks=profile.best_hooks,
            best_posting_times=profile.best_posting_times,
            engagement_trends=profile.engagement_trends,
            repeated_themes=profile.repeated_themes,
            content_fatigue=profile.content_fatigue
        )
        # Deactivate old profiles
        old_profiles = self.session.query(ContentStrategyProfileModel).filter_by(is_active=True).all()
        for p in old_profiles:
            p.is_active = False
            
        self.session.add(model)
        self.session.commit()
        return model

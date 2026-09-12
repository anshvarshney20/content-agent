import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from initials_agent.db.models import PublishedPostModel


class PublishingRepository:
    def __init__(self, session: Session):
        self.session = session
        
    def record_result(self, draft_id: uuid.UUID, platform: str, external_id: str, url: str = "") -> uuid.UUID:
        post = PublishedPostModel(
            draft_id=draft_id,
            platform=platform,
            external_id=external_id,
            url=url,
            published_at=datetime.now(UTC)
        )
        self.session.add(post)
        self.session.commit()
        return post.id
        
    def get_published_by_draft(self, draft_id: uuid.UUID) -> list[PublishedPostModel]:
        return self.session.query(PublishedPostModel).filter_by(draft_id=draft_id).all()

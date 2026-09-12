from sqlalchemy.orm import Session

from initials_agent.db.models import ContentDraftModel, TopicModel


class TopicRepository:
    def __init__(self, session: Session):
        self.session = session

    def record_topic(self, title: str, angle: str, score: float):
        # Optional helper for tests / tooling. Agent owns draft-linked TopicModel rows.
        # Flush only — never commit mid-pipeline.
        topic = TopicModel(title=title, angle=angle, score=score)
        self.session.add(topic)
        self.session.flush()

    def get_recent_topics(self, limit: int = 50) -> list[str]:
        topics = (
            self.session.query(TopicModel)
            .order_by(TopicModel.created_at.desc())
            .limit(limit)
            .all()
        )
        return [t.title for t in topics if t.title]

    def get_recent_draft_titles(self, limit: int = 40) -> list[str]:
        drafts = (
            self.session.query(ContentDraftModel)
            .order_by(ContentDraftModel.created_at.desc())
            .limit(limit)
            .all()
        )
        out: list[str] = []
        for d in drafts:
            if d.title:
                out.append(d.title)
            if d.hook:
                out.append(d.hook)
            refs = d.source_references or []
            if isinstance(refs, list):
                out.extend(str(x) for x in refs if x)
        return out

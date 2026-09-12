import pytest
import uuid
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from initials_agent.db.models import Base, TopicModel, ContentDraftModel, QualityCheckModel, GeneratedAssetModel
from initials_agent.repositories.approval import ApprovalRepository
from initials_agent.services.approval.local import LocalApprovalService
from initials_agent.models.workflow import ApprovalStatus

@pytest.fixture
def memory_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def populated_db(memory_db):
    topic = TopicModel(title="Test Topic")
    memory_db.add(topic)
    memory_db.commit()
    
    draft = ContentDraftModel(
        topic_id=topic.id,
        title="Draft Title",
        hook="Hook",
        linkedin_post="LI Content",
        instagram_caption="IG Content",
        cta="Click here",
        hashtags=["test"],
        source_references=["https://example.com"],
        state="draft"
    )
    memory_db.add(draft)
    memory_db.commit()
    
    qc = QualityCheckModel(
        draft_id=draft.id,
        passed=True,
        status="pass",
        score=95.5,
        errors=[],
        warnings=["Some warning"],
        improvements=[],
        checked_at=datetime.now(timezone.utc)
    )
    asset = GeneratedAssetModel(
        draft_id=draft.id,
        url="https://example.com/image.jpg",
        asset_type="image"
    )
    memory_db.add(qc)
    memory_db.add(asset)
    memory_db.commit()
    
    return memory_db, draft.id

def test_approval_flow(populated_db):
    session, draft_id = populated_db
    repo = ApprovalRepository(session)
    service = LocalApprovalService(repo)
    
    # Create request
    req_id = repo.submit_draft_for_approval(draft_id)
    assert req_id is not None
    
    # List pending
    pending = service.list_pending()
    assert len(pending) == 1
    req = pending[0]
    assert req.topic == "Test Topic"
    assert req.quality_score == 95.5
    assert req.warnings == ["Some warning"]
    assert req.image_path == "https://example.com/image.jpg"
    assert req.status == ApprovalStatus.PENDING
    
    # Show
    fetched = service.get_request(req_id)
    assert fetched.id == req_id
    
    # Approve
    service.approve(req_id)
    assert service.get_request(req_id).status == ApprovalStatus.APPROVED
    
    # Reject
    service.reject(req_id, "Bad")
    assert service.get_request(req_id).status == ApprovalStatus.REJECTED
    
    # Regenerate
    service.regenerate(req_id, "Fix tone")
    assert service.get_request(req_id).status == ApprovalStatus.REGENERATION_REQUESTED

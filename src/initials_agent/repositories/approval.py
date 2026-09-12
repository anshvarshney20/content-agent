import uuid

from sqlalchemy.orm import Session

from initials_agent.db.models import (
    ApprovalRequestModel,
)


class ApprovalRepository:
    def __init__(self, session: Session):
        self.session = session
        
    def submit_draft_for_approval(self, draft_id: uuid.UUID) -> uuid.UUID:
        req = ApprovalRequestModel(draft_id=draft_id, status="pending")
        self.session.add(req)
        self.session.commit()
        return req.id
        
    def get_pending_requests(self) -> list[ApprovalRequestModel]:
        return self.session.query(ApprovalRequestModel).filter_by(status="pending").all()
        
    def get_request(self, req_id: uuid.UUID) -> ApprovalRequestModel:
        return self.session.query(ApprovalRequestModel).filter_by(id=req_id).first()
        
    def update_status(self, req_id: uuid.UUID, status: str, notes: str = None):
        req = self.get_request(req_id)
        if req:
            req.status = status
            if notes:
                req.reviewer_notes = notes
            self.session.commit()

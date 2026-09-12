from enum import Enum


class ContentState(str, Enum):
    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"

class SocialPlatform(str, Enum):
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"

class QualityStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    NEEDS_REVISION = "needs_revision"

class ApprovalStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REGENERATION_REQUESTED = "regeneration_requested"

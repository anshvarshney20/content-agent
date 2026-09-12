from pydantic import BaseModel


class LLMQualityReview(BaseModel):
    factual_consistency_score: int
    unsupported_statistics: bool
    invented_quotes: bool
    brand_voice_score: int
    brand_visual_requirements_met: bool
    grammar_score: int
    misleading_claims: bool
    excessive_promotional: bool
    cta_quality_score: int
    feedback_notes: list[str]
    duplicate_content_detected: bool

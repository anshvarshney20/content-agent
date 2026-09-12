import json

from pydantic import ValidationError

from initials_agent.models.content import ContentDraft
from initials_agent.models.quality import LLMQualityReview
from initials_agent.models.workflow import QualityCheck, QualityStatus
from initials_agent.providers.llm.base import LLMProvider
from initials_agent.services.quality.validators import run_deterministic_checks


class QualityControlService:
    def __init__(self, llm: LLMProvider, max_retries: int = 2):
        self.llm = llm
        self.max_retries = max_retries
        
    def _calculate_final_score(self, llm_review: LLMQualityReview, deterministic_errors: list[str]) -> (float, list[str]):
        errors = list(deterministic_errors)
        
        # Hard fail conditions
        if llm_review.unsupported_statistics:
            errors.append("LLM detected unsupported statistics.")
        if llm_review.invented_quotes:
            errors.append("LLM detected invented quotes.")
        if llm_review.misleading_claims:
            errors.append("LLM detected misleading claims.")
        if llm_review.excessive_promotional:
            errors.append("Excessive promotional language used.")
        if not llm_review.brand_visual_requirements_met:
            errors.append("Brand visual requirements were not met.")
        if llm_review.duplicate_content_detected:
            errors.append("Duplicate content detected by LLM.")
            
        base_score = (
            llm_review.factual_consistency_score * 0.4 +
            llm_review.brand_voice_score * 0.3 +
            llm_review.grammar_score * 0.2 +
            llm_review.cta_quality_score * 0.1
        )
        
        # Penalize for deterministic errors
        score = base_score - (len(errors) * 20.0)
        
        return max(0.0, score), errors

    async def check_quality(self, draft: ContentDraft, platform: str) -> QualityCheck:
        det_errors = run_deterministic_checks(draft, platform)
        
        # Build prompt for LLM review
        system_prompt = (
            "You are the Quality Control Agent for Daily Content Agent — a product that writes "
            "newsjack marketing for ANY customer brand (not one fixed company). "
            "Posts use external news as a hook, then a brand bridge and CTA promoting that customer's offer. "
            "A clear brand bridge + CTA grounded in the customer's stated offer is EXPECTED and is NOT "
            "excessive_promotional. "
            "Set excessive_promotional=true ONLY for hard-sell spam, fake urgency, invented testimonials, "
            "or claiming the brand is the company featured in the news article. "
            "Still hard-fail unsupported statistics, invented quotes, and misleading claims. "
            "Review factual integrity and brand voice."
        )
        user_prompt = (
            f"Review this draft for {platform}:\n"
            f"Title: {draft.title}\n"
            f"Content: {draft.linkedin_post if platform == 'linkedin' else draft.instagram_caption}\n"
            f"CTA: {draft.cta}\n"
            f"Concept: {draft.visual_concept.model_dump_json() if draft.visual_concept else 'None'}"
        )
        
        llm_review = None
        for attempt in range(self.max_retries):
            try:
                llm_review = await self.llm.generate_json(user_prompt, system_prompt, LLMQualityReview)
                break
            except (ValueError, ValidationError, json.JSONDecodeError) as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError("Failed to run LLM quality check")
                user_prompt += f"\nError: {e}. Output valid JSON."

        final_score, errors = self._calculate_final_score(llm_review, det_errors)
        
        if final_score < 60 or errors:
            status = QualityStatus.FAIL
            passed = False
        elif final_score < 80:
            status = QualityStatus.NEEDS_REVISION
            passed = False
        else:
            status = QualityStatus.PASS
            passed = True
            
        return QualityCheck(
            passed=passed,
            status=status,
            score=final_score,
            errors=errors,
            warnings=[],
            improvements=llm_review.feedback_notes
        )

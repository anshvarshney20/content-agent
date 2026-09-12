

from .base import LLMProvider, T


class MockLLMProvider(LLMProvider):
    def __init__(self, should_fail_first_time: bool = False, return_data: dict = None):
        self.should_fail_first_time = should_fail_first_time
        self.return_data = return_data
        self.attempts = 0

    async def generate_json(self, prompt: str, system_prompt: str, schema: type[T]) -> T:
        self.attempts += 1
        if self.should_fail_first_time and self.attempts == 1:
            raise ValueError("Mock JSON decode error or validation error")
            
        if self.return_data:
            return schema.model_validate(self.return_data)
            
        if schema.__name__ == "VisualConcept":
            ar = "1080x1350"
            if "1200x1200" in prompt:
                ar = "1200x1200"
            default_data = {
                "aspect_ratio": ar,
                "composition": "High contrast, strong hierarchy",
                "headline": "AI Automation in 2026",
                "supporting_text": "Enterprise Technology",
                "visual_subject": "Abstract neural network",
                "environment": "Dark server room",
                "lighting": "Cinematic electric blue accent",
                "color_palette": "Black, electric blue, neon purple",
                "typography": "Clean modern sans-serif",
                "negative_prompt": "Generic robots, clichés, stock imagery",
                "brand_requirements": "Customer brand identity"
            }
        elif schema.__name__ == "LLMQualityReview":
            default_data = {
                "factual_consistency_score": 95,
                "unsupported_statistics": False,
                "invented_quotes": False,
                "brand_voice_score": 90,
                "brand_visual_requirements_met": True,
                "grammar_score": 100,
                "misleading_claims": False,
                "excessive_promotional": False,
                "cta_quality_score": 90,
                "feedback_notes": ["Good work."],
                "duplicate_content_detected": False
            }
        elif schema.__name__ == "ContentStrategyProfile":
            default_data = {
                "strongest_topics": ["AI Agents", "Automation"],
                "weakest_topics": ["General Marketing"],
                "strongest_formats": ["Carousel"],
                "best_hooks": ["Stop doing X"],
                "best_posting_times": ["09:00", "17:00"],
                "engagement_trends": ["Increasing on technical depth"],
                "repeated_themes": ["AI replacing jobs"],
                "content_fatigue": ["Generic AI art"]
            }
        else:
            default_data = {
                "title": "Mock Title for Agent",
                "hook": "This is a mock hook that exceeds ten chars.",
                "linkedin_post": "This is a professional and insightful post for LinkedIn, satisfying the minimum length of fifty characters easily.",
                "instagram_caption": "This is a visual and concise mock caption for Instagram, satisfying fifty chars minimum limit.",
                "cta": "Read more on our blog.",
                "hashtags": ["mock", "test"],
                "source_references": ["https://example.com"]
            }
        return schema.model_validate(default_data)

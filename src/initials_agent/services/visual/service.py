import json
import logging
import uuid

from pydantic import ValidationError

from initials_agent.config import get_settings
from initials_agent.models.content import (
    ContentDraft,
    GeneratedAsset,
    InstagramCarouselPlan,
    VisualConcept,
)
from initials_agent.providers.llm.base import LLMProvider
from initials_agent.services.image_generation.service import ImageGenerationService

logger = logging.getLogger(__name__)

_SLIDE_ROLES_BY_COUNT = {
    2: ["hook", "cta"],
    3: ["hook", "insight", "cta"],
    4: ["hook", "insight", "bridge", "cta"],
    5: ["hook", "insight", "bridge", "detail", "cta"],
    6: ["hook", "insight", "bridge", "detail", "proof", "cta"],
    7: ["hook", "insight", "bridge", "detail", "proof", "offer", "cta"],
}


class VisualContentService:
    def __init__(self, llm: LLMProvider, image_service: ImageGenerationService, max_retries: int = 1):
        self.llm = llm
        self.image_service = image_service
        self.max_retries = max_retries

    def _brand_block(self) -> tuple[dict, str]:
        from initials_agent.product.profile import load_profile

        brand = load_profile().brand_config()
        name = brand["name"]
        offer = brand.get("offer") or brand.get("positioning", "")
        return brand, f"""
Brand Positioning: {brand.get('positioning', '')}
What they sell: {offer}
Niche: {brand.get('niche_label', '')}

Visual style: premium modern technology / business (or match brand category)
Background: dark / black or brand-appropriate atmosphere
Accent: electric blue and cyan (or brand accents)
Typography: clean modern sans-serif
Mood: intelligent, cinematic, technical, ambitious, premium
Composition: high contrast, minimal clutter, strong hierarchy

AVOID:
- generic AI robots, random humanoid robots
- cheap stock imagery
- overly saturated cyberpunk
- generic motivational graphics, visual clichés
- unrelated futuristic objects
- any brand name other than {name}

CRITICAL RULE:
NEVER put unsupported statistics or factual claims into an image text.
"""

    def _build_system_prompt(self) -> str:
        brand, style = self._brand_block()
        name = brand["name"]
        return f"""
You are the expert Visual Content Agent for {name}.
{style}
Respond ONLY with valid JSON matching the VisualConcept schema.
"""

    def _build_user_prompt(self, draft: ContentDraft, platform: str) -> str:
        if platform.lower() == "instagram":
            aspect_ratio = "1080x1350"
            text_context = draft.instagram_caption
        else:
            aspect_ratio = "1200x1200"
            text_context = draft.linkedin_post

        return f"""
Please design a visual concept for the following content draft to be published on {platform}.
Target Aspect Ratio: {aspect_ratio}

Draft Title: {draft.title}
Hook: {draft.hook}
Content context: {text_context}

Ensure the headline and supporting text used in the image are catchy but strictly factual based on the content.
"""

    def _carousel_system_prompt(self, slide_count: int) -> str:
        brand, style = self._brand_block()
        name = brand["name"]
        roles = _SLIDE_ROLES_BY_COUNT.get(slide_count) or (
            ["hook"] + ["detail"] * max(0, slide_count - 2) + ["cta"]
        )
        role_line = ", ".join(f"slide {i + 1}={r}" for i, r in enumerate(roles))
        return f"""
You are the expert Visual Content Agent for {name}.
Design a SWIPEABLE Instagram carousel ({slide_count} slides). Each slide must feel like the next card in one story — not duplicate posters.

{style}

Required slide roles in order: {role_line}
- hook: attention-grabbing cover — short punchy headline
- insight: what the story means
- bridge: connect story to what {name} offers
- detail/proof/offer: supporting beat without fake stats
- cta: clear next step + brand name {name}

Each slide: different visual_subject + composition; short on-image text (headline max ~6 words).
Respond ONLY with valid JSON matching InstagramCarouselPlan (slides array length exactly {slide_count}).
"""

    def _carousel_user_prompt(self, draft: ContentDraft, slide_count: int) -> str:
        return f"""
Create a {slide_count}-slide Instagram carousel plan for this draft.
Aspect for every slide: 1080x1350 portrait feed.

Title: {draft.title}
Hook: {draft.hook}
Instagram caption context:
{draft.instagram_caption}

CTA: {draft.cta}

Slides must read left-to-right as a swipe story (cover → value → brand → CTA).
"""

    def _slide_to_concept(self, slide, brand_name: str) -> VisualConcept:
        return VisualConcept(
            aspect_ratio="1080x1350",
            composition=slide.composition,
            headline=slide.headline,
            supporting_text=slide.supporting_text,
            visual_subject=slide.visual_subject,
            environment="premium brand atmosphere, shallow depth, editorial framing",
            lighting="cinematic soft key light, high contrast accents",
            color_palette="brand-aligned premium palette, high contrast",
            typography="clean modern sans-serif, large readable headline",
            negative_prompt=(
                "clutter, watermarks, fake logos, unsupported statistics, "
                "generic stock people montage, illegible text"
            ),
            brand_requirements=(
                f"Slide {slide.slide_index} ({slide.role}) for {brand_name}. "
                "Carousel continuity; distinct from other slides."
            ),
        )

    async def _create_single(self, draft: ContentDraft, platform: str) -> GeneratedAsset:
        # Skip VisualConcept LLM — it often fails JSON validation and delayed Puter
        # until the pipeline gave up. Fallback prompt is enough for reliable images.
        concept = self._fallback_concept(draft, platform)
        asset = await self.image_service.generate(
            uuid.uuid4(), concept, asset_type=f"{platform.lower()}_image"
        )
        draft.visual_concept = concept
        return asset

    def _fallback_concept(self, draft: ContentDraft, platform: str) -> VisualConcept:
        from initials_agent.product.profile import load_profile

        name = load_profile().brand_config().get("name", "Brand")
        aspect = "1080x1350" if platform.lower() == "instagram" else "1200x1200"
        return VisualConcept(
            aspect_ratio=aspect,
            composition="clean premium editorial, strong focal subject, minimal clutter",
            headline=(draft.hook or draft.title or name)[:80],
            supporting_text=(draft.cta or "")[:120],
            visual_subject=(
                f"Premium brand visual for {name}. Theme: {draft.title}. "
                "Cinematic lighting, modern, high contrast, no fake logos."
            ),
            environment="brand-appropriate atmosphere",
            lighting="soft cinematic key light",
            color_palette="brand-aligned premium dark palette",
            typography="clean modern sans-serif",
            negative_prompt="watermarks, illegible text, clutter, stock clichés",
            brand_requirements=f"For {name} only",
        )

    async def _create_instagram_carousel(self, draft: ContentDraft) -> list[GeneratedAsset]:
        settings = get_settings()
        slide_count = int(settings.instagram.carousel_slides or 2)
        slide_count = max(1, min(7, slide_count))

        # Single image = fastest / most reliable with Puter
        if slide_count == 1:
            asset = await self._create_single(draft, "instagram")
            return [asset]

        from initials_agent.product.profile import load_profile

        brand_name = load_profile().brand_config().get("name", "Brand")
        system_prompt = self._carousel_system_prompt(slide_count)
        user_prompt = self._carousel_user_prompt(draft, slide_count)

        plan = None
        for attempt in range(max(self.max_retries, 2)):
            try:
                plan = await self.llm.generate_json(
                    user_prompt, system_prompt, InstagramCarouselPlan
                )
                if len(plan.slides) < 2:
                    raise ValueError("Carousel needs at least 2 slides")
                break
            except (ValueError, ValidationError, json.JSONDecodeError) as e:
                if attempt == max(self.max_retries, 2) - 1:
                    logger.warning("Carousel plan failed — falling back to single Instagram image: %s", e)
                    return [await self._create_single(draft, "instagram")]
                user_prompt += (
                    f"\n\nPrevious attempt failed: {e!s}. "
                    f"Return InstagramCarouselPlan with exactly {slide_count} slides."
                )

        slides = sorted(plan.slides, key=lambda s: s.slide_index)[:slide_count]
        assets: list[GeneratedAsset] = []
        for i, slide in enumerate(slides, start=1):
            slide.slide_index = i
            concept = self._slide_to_concept(slide, brand_name)
            logger.info(
                "Generating Instagram carousel slide %s/%s (%s): %s",
                i,
                len(slides),
                slide.role,
                slide.headline[:60],
            )
            try:
                asset = await self.image_service.generate(
                    uuid.uuid4(), concept, asset_type=f"instagram_carousel_{i}"
                )
                assets.append(asset)
                if i == 1:
                    draft.visual_concept = concept
            except Exception as exc:
                logger.warning(
                    "Carousel slide %s/%s failed (continuing with other slides): %s",
                    i,
                    len(slides),
                    exc,
                )

        if not assets:
            logger.warning("All carousel slides failed — falling back to single Instagram image")
            return [await self._create_single(draft, "instagram")]
        return assets

    async def create_visuals(self, draft: ContentDraft, platforms: list[str]) -> list[GeneratedAsset]:
        assets: list[GeneratedAsset] = []
        # LinkedIn first (one image), then Instagram — so we often keep at least one asset
        ordered = sorted(
            platforms,
            key=lambda p: 0 if p.lower() == "linkedin" else 1,
        )
        for platform in ordered:
            try:
                if platform.lower() == "instagram":
                    ig_assets = await self._create_instagram_carousel(draft)
                    assets.extend(ig_assets)
                else:
                    assets.append(await self._create_single(draft, platform))
            except Exception as exc:
                logger.warning("Visuals for %s failed (other platforms may still work): %s", platform, exc)

        if not assets:
            # Last resort: one Instagram single shot
            try:
                logger.warning("Retrying one single Instagram image as last resort")
                assets.append(await self._create_single(draft, "instagram"))
            except Exception as exc:
                raise RuntimeError(
                    "No images generated. Puter timed out or failed. "
                    "Check Node.js, IMAGE__API_KEY, or set IMAGE__PROVIDER=mock for a placeholder."
                ) from exc
        draft.assets.extend(assets)
        return assets

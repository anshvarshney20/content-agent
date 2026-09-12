import json

from pydantic import ValidationError

from initials_agent.models.content import ContentDraft
from initials_agent.models.research import ResearchResult
from initials_agent.providers.llm.base import LLMProvider
from initials_agent.services.strategist.service import StrategistDecision


class ContentWriterService:
    def __init__(self, llm: LLMProvider, max_retries: int = 3):
        self.llm = llm
        self.max_retries = max_retries

    def _build_system_prompt(self, brand_config: dict) -> str:
        name = brand_config.get("name", "Your Brand")
        positioning = brand_config.get(
            "positioning",
            "Help customers solve real problems with clear, practical content.",
        )
        audience = brand_config.get("audience", "Business professionals")
        voice = brand_config.get("voice", "Confident, practical, clear")
        niche = brand_config.get("niche_label", "General business")
        offer = brand_config.get("offer") or positioning
        proof = brand_config.get("proof_points") or ""
        cta = brand_config.get("cta_text") or "Book a demo"
        website = brand_config.get("website_url") or ""
        if proof:
            proof_line = (
                f"- Proof points (use only if relevant, do not invent more): {proof}"
            )
        else:
            proof_line = (
                "- Proof points: none provided — do not invent case studies, logos, or metrics."
            )
        if website:
            website_line = f"- Website for CTA (optional): {website}"
            cta_extra = " and include the website URL"
        else:
            website_line = "- Website: none — do not invent a URL."
            cta_extra = ""

        return f"""
You are the expert marketing copywriter for {name}.
Your job is STORY-BASED NEWSJACKING: take THIS specific external article and turn it into
brand marketing for {name}. Every post must feel unique to that story — not a reusable template.

You are NOT a news commentator and NOT a press-release rewriter for the company in the article.
The article is bait; {name}'s offer is what you promote.

Brand Positioning: {positioning}
What we sell / offer: {offer}
Audience: {audience}
Content niche focus: {niche}
{proof_line}
Default CTA: {cta}
{website_line}

BRAND VOICE:
- {voice}
- Business-focused, modern, intelligent, persuasive without hype spam

MARKETING STRUCTURE (required for LinkedIn and Instagram):
1. HOOK (FACT) — open on THIS article's concrete event, company, product, regulation, or shift.
   Name what happened. Attribute the source. Do not claim {name} is the company in the article.
2. INSIGHT (INTERPRETATION) — explain what THIS specific story means for {audience}.
   The insight must reference elements from the story (e.g. regulation, launch, outage, funding,
   acquisition, security event). Ban generic lines like "winners will turn this into a workflow"
   unless they are grounded in this story.
3. BRAND BRIDGE — connect THAT story's tension to what {name} sells ({offer}).
   Explicitly link story theme → customer pain → {name}'s offer.
   Example shape: "When [story beat] happens, [audience] need [capability]. That is what we do at {name}: {offer}."
   Never invent fake customer wins, fake case studies, or claim you caused the news.
4. CTA — end with the provided CTA text{cta_extra}.

STRICT RULES:
- The brand bridge MUST change with the article. Two different stories must produce two different bridges.
- Do not claim {name} wrote, launched, or is featured in the source article.
- Do not invent statistics, quotes, testimonials, client names, or awards.
- Do not use generic motivational spam or excessive emojis.
- Do not copy source article text; rewrite originally.
- Distinguish FACT vs INTERPRETATION vs OPINION. Never present interpretation as fact.
- Promote only from the offer / proof points / CTA above.
- Soft sell is expected and correct; hard-sell spam and fake urgency are not.
- Write as {name} — never invent a different brand name.
- LinkedIn: professional marketing narrative (hook, insight, bridge, CTA), 3-5 short paragraphs.
- Instagram: write for a SWIPEABLE carousel post — short lines, hook first, story-specific bridge, CTA;
  include a natural “swipe” cue (e.g. Swipe →) so the caption matches multi-slide visuals; hashtags stored separately.

Respond ONLY with valid JSON matching the provided schema.

OUTPUT REQUIREMENTS:
- title: short label rooted in THIS article
- hook: story-specific opening line
- linkedin_post: ready to paste (news hook, insight, brand bridge, CTA). No fake stats.
- instagram_caption: ready to paste for a carousel (short lines, hook first, swipe cue, bridge, CTA).
- cta: short call-to-action string aligned with Default CTA.
- Keep news claims grounded in the provided article details/sources.
"""

    def _build_user_prompt(self, decision: StrategistDecision, research: ResearchResult) -> str:
        source_bits = []
        for src in research.sources or []:
            bit = f"- {src.title} ({src.url})"
            snippet = (getattr(src, "snippet", None) or "").strip()
            if snippet:
                bit += f"\n  Story detail: {snippet}"
            source_bits.append(bit)
        sources_block = "\n".join(source_bits) if source_bits else ", ".join(
            str(u) for u in decision.source_urls
        )

        return f"""
Draft STORY-SPECIFIC marketing posts that newsjack THIS article for the customer's brand
(from the system prompt — any business):

Selected Topic / Article headline: {decision.selected_topic}
Content Angle: {decision.content_angle}
Recommended Format: {decision.recommended_format}
Reasoning (why this story): {decision.reason}

Article context (use this — do not ignore it):
{research.summary}

Sources:
{sources_block}

Write READY-TO-PUBLISH LinkedIn + Instagram posts.
Requirements:
- Hook must name the concrete story beat from this article.
- Insight must be about THIS story for the brand's audience.
- Brand bridge must connect THIS story's theme to the brand offer (not a stock sentence).
- CTA from the system prompt.
Do not wrap in markdown. Do not invent statistics.
Do not assume a specific company beyond the brand fields provided.
"""

    async def write_draft(
        self, decision: StrategistDecision, research: ResearchResult, brand_config: dict
    ) -> ContentDraft:
        system_prompt = self._build_system_prompt(brand_config)
        user_prompt = self._build_user_prompt(decision, research)

        for attempt in range(self.max_retries):
            try:
                draft = await self.llm.generate_json(user_prompt, system_prompt, ContentDraft)
                return draft
            except (ValueError, ValidationError, json.JSONDecodeError) as e:
                if attempt == self.max_retries - 1:
                    raise RuntimeError(
                        f"Failed to generate valid content draft after {self.max_retries} attempts: {e}"
                    )
                user_prompt += (
                    f"\n\nPrevious attempt failed with error: {e!s}. "
                    "Please correct the issue and output valid JSON matching the schema."
                )

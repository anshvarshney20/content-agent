from datetime import UTC, datetime
import re

from pydantic import BaseModel, HttpUrl

from initials_agent.models.research import ResearchResult, ResearchSource
from initials_agent.repositories.topics import TopicRepository


class StrategistDecision(BaseModel):
    selected_topic: str
    reason: str
    score: float
    source_urls: list[HttpUrl]
    content_angle: str
    recommended_format: str


def _normalize_title(title: str) -> str:
    text = (title or "").lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " ".join(text.split())


def _is_used_topic(title: str, recent_topics: list[str]) -> bool:
    """Hard block exact / near-duplicate headlines already used."""
    norm = _normalize_title(title)
    if not norm:
        return False
    words = set(norm.split())
    for recent in recent_topics:
        rnorm = _normalize_title(recent)
        if not rnorm:
            continue
        if norm == rnorm or norm in rnorm or rnorm in norm:
            return True
        rwords = set(rnorm.split())
        if not words or not rwords:
            continue
        overlap = len(words & rwords) / len(words | rwords)
        if overlap >= 0.55:
            return True
    return False


class ContentStrategistService:
    def __init__(self, repo: TopicRepository):
        self.repo = repo

    def determine_format_and_angle(self, source: ResearchSource) -> tuple[str, str]:
        title = source.title.lower()
        if "how to" in title or "guide" in title or "what is" in title:
            return "educational post", "Educational breakdown of the technology"
        elif "startup" in title or "business" in title or "enterprise" in title:
            return "business use case", "How businesses can apply this AI effectively"
        elif "founder" in title:
            return "founder perspective", "A founder's perspective on this trend"
        elif "diagram" in title or "architecture" in title or "model" in title:
            return "single image", "Technical architecture breakdown"
        else:
            return "technology breakdown", "Simplifying the technical advancement"

    def select_topic(
        self,
        results: list[ResearchResult],
        focus_terms: list[str] | None = None,
        exclude_titles: list[str] | None = None,
    ) -> StrategistDecision:
        recent = list(self.repo.get_recent_topics(limit=80))
        if exclude_titles:
            recent.extend(exclude_titles)
        recent.extend(self.repo.get_recent_draft_titles(limit=40))

        best_source = None
        best_score = -9999.0
        skipped = 0

        for res in results:
            for source in res.sources:
                if _is_used_topic(source.title, recent):
                    skipped += 1
                    continue
                score = self.score_source(source, recent, focus_terms=focus_terms)
                if score > best_score:
                    best_score = score
                    best_source = source

        if not best_source:
            raise ValueError(
                "No fresh topics left — every RSS story was already used recently. "
                f"Skipped {skipped} duplicate(s). Try again later or change niche."
            )

        fmt, angle = self.determine_format_and_angle(best_source)

        return StrategistDecision(
            selected_topic=best_source.title,
            reason=(
                f"Highest score ({best_score}) among unused stories"
                + (f"; skipped {skipped} already-used" if skipped else "")
            ),
            score=best_score,
            source_urls=[best_source.url],
            content_angle=angle,
            recommended_format=fmt,
        )

    def score_source(
        self,
        source: ResearchSource,
        recent_topics: list[str],
        focus_terms: list[str] | None = None,
    ) -> float:
        score = 0.0
        title = source.title.lower()

        ai_terms = [
            "ai",
            "digital",
            "transformation",
            "generative",
            "llm",
            "agent",
            "robotics",
            "automation",
            "cybersecurity",
            "cloud",
        ]
        score += sum(2.0 for t in ai_terms if t in title)

        biz_terms = [
            "startup",
            "business",
            "founder",
            "roi",
            "efficiency",
            "market",
            "enterprise",
        ]
        score += sum(2.0 for t in biz_terms if t in title)

        if focus_terms:
            for term in focus_terms:
                t = term.lower().strip()
                if len(t) > 2 and t in title:
                    score += 4.0

        if source.published_date:
            age = (datetime.now(UTC) - source.published_date).total_seconds() / 3600
            if age < 24:
                score += 20.0
            elif age < 72:
                score += 10.0
        else:
            score -= 10.0

        if "?" in source.title or "vs" in title:
            score += 5.0

        if "how to" in title or "guide" in title or "what" in title:
            score += 5.0

        if "innovation" in title or "intelligent system" in title:
            score += 10.0

        score += source.credibility_score * 20.0
        if source.credibility_score < 0.5:
            score -= 20.0

        visual_terms = ["robot", "architecture", "diagram", "vision", "model", "platform"]
        score += sum(2.0 for t in visual_terms if t in title)

        risk_terms = ["rumor", "leak", "unverified", "claim", "might", "could"]
        if any(r in title for r in risk_terms):
            score -= 30.0

        title_words = set(title.split())
        for r_top in recent_topics:
            r_words = set(r_top.lower().split())
            overlap = len(title_words.intersection(r_words))
            if overlap > 2:
                score -= 40.0

        return score

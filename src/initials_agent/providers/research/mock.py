from datetime import UTC, datetime, timedelta

from .base import RawSearchResult, ResearchProvider


class MockResearchProvider(ResearchProvider):
    """Niche-shaped fallback when live RSS has no matching headlines."""

    async def search(self, query: str, limit: int = 5) -> list[RawSearchResult]:
        now = datetime.now(UTC)
        q = (query or "business technology").strip()
        short = " ".join(q.split()[:6]) or "business technology"
        return [
            RawSearchResult(
                title=f"What’s changing in {short} this week",
                url="https://example.com/niche-briefing",
                summary=(
                    f"Operators tracking {short} are watching practical workflow shifts, "
                    "not hype. This briefing focuses on what can ship this quarter."
                ),
                published_date=now - timedelta(hours=6),
                source_domain="example.com",
            ),
            RawSearchResult(
                title=f"How teams apply {short} without bloated tooling",
                url="https://example.com/niche-playbook",
                summary=(
                    f"A practical look at {short}: where automation helps, where humans "
                    "still approve, and how to measure cycle-time impact."
                ),
                published_date=now - timedelta(days=1),
                source_domain="example.com",
            ),
            RawSearchResult(
                title=f"Buyer checklist for {short} investments",
                url="https://example.com/niche-checklist",
                summary=(
                    f"Before buying into {short}, separate demos from durable workflows "
                    "and decide what still needs human review."
                ),
                published_date=now - timedelta(days=2),
                source_domain="example.com",
            ),
        ][:limit]

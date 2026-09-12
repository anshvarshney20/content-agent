from datetime import UTC, datetime, timedelta

from initials_agent.models import ResearchResult, ResearchSource
from initials_agent.providers.research.base import ResearchProvider
from initials_agent.providers.research.rss import DOMAIN_CREDIBILITY


class ResearchService:
    def __init__(self, provider: ResearchProvider):
        self.provider = provider
        
    async def conduct_research(self, query: str, limit: int = 5, max_age_days: int = 30) -> ResearchResult:
        # Request a larger batch to account for duplication and staleness drops
        raw_results = await self.provider.search(query, limit=limit * 3)
        
        seen_urls = set()
        valid_sources = []
        combined_summaries = []
        
        now = datetime.now(UTC)
        
        for item in raw_results:
            url_str = str(item.url)
            
            # Deduplicate results
            if url_str in seen_urls:
                continue
                
            # Reject obviously stale results
            if item.published_date and (now - item.published_date) > timedelta(days=max_age_days):
                continue
                
            seen_urls.add(url_str)
            
            domain = item.source_domain.lower()
            credibility = 0.55 if "example" in domain else DOMAIN_CREDIBILITY.get(domain, 0.72)
            
            source = ResearchSource(
                url=item.url,
                title=item.title,
                published_date=item.published_date,
                credibility_score=credibility,
                snippet=(item.summary or item.title)[:500],
            )
            
            valid_sources.append(source)
            combined_summaries.append(f"[{item.source_domain}] {item.title}: {item.summary}")
            
            if len(valid_sources) >= limit:
                break
                
        final_summary = "\n\n".join(combined_summaries) if combined_summaries else "No recent developments found."
        
        return ResearchResult(
            query=query,
            summary=final_summary,
            sources=valid_sources
        )

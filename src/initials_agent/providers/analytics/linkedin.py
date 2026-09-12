from initials_agent.models.analytics import AnalyticsSnapshot

from .base import AnalyticsProvider


class LinkedInAnalyticsProvider(AnalyticsProvider):
    async def get_post_analytics(self, external_id: str) -> AnalyticsSnapshot:
        # In a real implementation, this would call the LinkedIn API
        # GET https://api.linkedin.com/v2/organizationalEntityShareStatistics
        return AnalyticsSnapshot()

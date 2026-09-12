from initials_agent.models.analytics import AnalyticsSnapshot

from .base import AnalyticsProvider


class InstagramAnalyticsProvider(AnalyticsProvider):
    async def get_post_analytics(self, external_id: str) -> AnalyticsSnapshot:
        # In a real implementation, this would call the Instagram Graph API
        # GET https://graph.facebook.com/v17.0/{external_id}/insights
        return AnalyticsSnapshot()

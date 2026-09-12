from abc import ABC, abstractmethod

from initials_agent.models.analytics import AnalyticsSnapshot


class AnalyticsProvider(ABC):
    @abstractmethod
    async def get_post_analytics(self, external_id: str) -> AnalyticsSnapshot:
        """Fetch current analytics for a given post ID on this platform"""

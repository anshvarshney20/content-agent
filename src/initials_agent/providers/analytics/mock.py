import random

from initials_agent.models.analytics import AnalyticsSnapshot

from .base import AnalyticsProvider


class MockAnalyticsProvider(AnalyticsProvider):
    async def get_post_analytics(self, external_id: str) -> AnalyticsSnapshot:
        # Generate some dummy data for tests
        return AnalyticsSnapshot(
            impressions=random.randint(100, 10000),
            reach=random.randint(80, 8000),
            likes=random.randint(10, 500),
            comments=random.randint(0, 50),
            shares=random.randint(0, 20),
            clicks=random.randint(5, 100),
            engagement_rate=random.uniform(0.01, 0.1)
        )

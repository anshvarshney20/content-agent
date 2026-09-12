import logging

from initials_agent.models.analytics import ContentStrategyProfile
from initials_agent.providers.analytics.base import AnalyticsProvider
from initials_agent.providers.llm.base import LLMProvider
from initials_agent.repositories.analytics import AnalyticsRepository

logger = logging.getLogger(__name__)

class AnalyticsService:
    def __init__(self, linkedin_prov: AnalyticsProvider, instagram_prov: AnalyticsProvider, repo: AnalyticsRepository, llm: LLMProvider):
        self.linkedin_prov = linkedin_prov
        self.instagram_prov = instagram_prov
        self.repo = repo
        self.llm = llm

    async def sync_all(self):
        """Poll all published posts and sync their analytics."""
        posts = self.repo.get_published_posts()
        logger.info(f"Syncing analytics for {len(posts)} published posts...")
        
        for post in posts:
            try:
                if post.platform.lower() == "linkedin":
                    snap = await self.linkedin_prov.get_post_analytics(post.external_id)
                elif post.platform.lower() == "instagram":
                    snap = await self.instagram_prov.get_post_analytics(post.external_id)
                else:
                    continue
                
                self.repo.save_snapshot(post.id, snap)
                logger.info(f"Synced snapshot for {post.platform} post {post.external_id}")
            except Exception as e:
                logger.error(f"Failed to sync analytics for post {post.id}: {e}")

    async def generate_report(self) -> ContentStrategyProfile:
        """Analyze historical performance and generate a content strategy profile update."""
        # 1. Gather historical data
        posts = self.repo.get_published_posts()
        
        # Rule: Require minimum sample sizes before making strong recommendations.
        if len(posts) < 5:
            logger.warning("Insufficient data (minimum 5 posts) to run meaningful analysis. Aborting strategy update.")
            raise ValueError("Insufficient data for analytics report. Need at least 5 posts.")
            
        # Construct summary payload for LLM
        history = []
        for post in posts:
            if not post.analytics:
                continue
            # Get latest snapshot
            latest_snap = sorted(post.analytics, key=lambda a: a.recorded_at, reverse=True)[0]
            history.append({
                "platform": post.platform,
                "topic": post.draft.topic.title,
                "hook": post.draft.hook,
                "published_at": str(post.published_at),
                "impressions": latest_snap.impressions,
                "likes": latest_snap.likes,
                "engagement_rate": latest_snap.engagement_rate
            })

        system_prompt = (
            "You are an expert Data Analyst and Content Strategist for a customer's brand "
            "(any business using Daily Content Agent — not a single fixed company). "
            "Analyze the provided post analytics. "
            "CRITICAL RULES: "
            "1. Identify the strongest and weakest topics, formats, and hooks. "
            "2. Identify engagement trends and content fatigue. "
            "3. DO NOT claim causation from insufficient data. Acknowledge variance. "
            "4. Require minimum sample sizes before making strong recommendations. "
            "5. Respect the customer's brand voice from their profile; do not invent a different brand identity."
        )
        
        prompt = f"Here is the historical performance data of recent posts:\n{history}\n\nGenerate a new ContentStrategyProfile based strictly on these metrics."
        
        profile = await self.llm.generate_json(prompt, system_prompt, ContentStrategyProfile)
        
        # Save profile
        self.repo.save_profile(profile)
        logger.info(f"Generated and saved new ContentStrategyProfile (ID: {profile.id})")
        return profile

import logging
import os

from initials_agent.config import get_settings
from initials_agent.daily import DAILY_TECH_QUERY
from initials_agent.providers.analytics.mock import MockAnalyticsProvider
from initials_agent.providers.image.dalle import DalleImageProvider
from initials_agent.providers.image.gemini import GeminiImageProvider
from initials_agent.providers.image.mock import MockImageProvider
from initials_agent.providers.image.openrouter import OpenRouterImageProvider
from initials_agent.providers.image.puter import PuterImageProvider
from initials_agent.providers.llm.openai import OpenAILLMProvider
from initials_agent.providers.llm.openrouter import OpenRouterLLMProvider
from initials_agent.providers.publishing.mock import MockSocialPublisher
from initials_agent.providers.research.rss import RssResearchProvider
from initials_agent.repositories.analytics import AnalyticsRepository
from initials_agent.repositories.approval import ApprovalRepository
from initials_agent.repositories.publishing import PublishingRepository
from initials_agent.repositories.topics import TopicRepository
from initials_agent.services.analytics.service import AnalyticsService
from initials_agent.services.approval.local import LocalApprovalService
from initials_agent.services.image_generation.service import ImageGenerationService
from initials_agent.services.publishing.service import PublishingService
from initials_agent.services.quality.service import QualityControlService
from initials_agent.services.research.service import ResearchService
from initials_agent.services.strategist.service import ContentStrategistService
from initials_agent.services.visual.service import VisualContentService
from initials_agent.services.writer.service import ContentWriterService
from initials_agent.agent import DailyContentAgent

logger = logging.getLogger(__name__)


def _ai_api_key() -> str:
    """OpenRouter/OpenAI key from Settings (tenant credentials), not shared .env for SaaS users."""
    from initials_agent.tenant import cred_get, current_user_id, load_credentials

    uid = current_user_id()
    if uid:
        creds = load_credentials(uid)
        key = _clean_secret(str(creds.get("ai_api_key") or ""))
        if key:
            return key
        # Optional: reuse OpenRouter image key only when AI provider is openrouter
        if (creds.get("ai_provider") or "openrouter").lower() == "openrouter":
            img_prov = (creds.get("image_provider") or "").lower()
            if img_prov == "openrouter":
                img = _clean_secret(str(creds.get("image_api_key") or ""))
                if img:
                    return img
        # Authenticated tenant: never fall through to shared server .env
        if uid != "local":
            return ""

    settings = get_settings()
    key = settings.ai.api_key.get_secret_value() if settings.ai.api_key else ""
    key = _clean_secret(key)
    if not key and (settings.image.provider or "").lower() == "openrouter" and settings.image.api_key:
        key = _clean_secret(settings.image.api_key.get_secret_value())
    return key


def _ai_provider_and_model() -> tuple[str, str]:
    from initials_agent.tenant import current_user_id, load_credentials

    settings = get_settings()
    uid = current_user_id()
    if uid:
        creds = load_credentials(uid)
        if creds.get("ai_provider") or creds.get("ai_model_name") or creds.get("ai_api_key"):
            provider = _clean_secret(str(creds.get("ai_provider") or "openrouter")).lower() or "openrouter"
            model = _clean_secret(str(creds.get("ai_model_name") or "")) or settings.ai.model_name
            return provider, model
        if uid != "local":
            return "openrouter", settings.ai.model_name
    return (settings.ai.provider or "openrouter").lower().strip(), settings.ai.model_name


def build_llm():
    """LLM is required for all generated copy — no hardcoded/heuristic writer."""
    key = _ai_api_key()
    provider, model = _ai_provider_and_model()
    if not key:
        raise RuntimeError(
            "AI API key required for content generation. "
            "Add your key in Settings (per account). "
            "Hardcoded/heuristic drafts are disabled."
        )
    if provider == "openrouter":
        logger.info("Using OpenRouter (%s) for draft generation", model)
        return OpenRouterLLMProvider(key, model)
    if provider == "openai":
        logger.info("Using OpenAI (%s) for draft generation", model)
        return OpenAILLMProvider(key, model)
    raise RuntimeError(
        f"Unsupported AI provider={provider!r}. Use 'openrouter' or 'openai'."
    )


def build_research():
    return ResearchService(RssResearchProvider())


def _clean_secret(value: str | None) -> str:
    return (value or "").strip().strip("'").strip('"')


# Legacy / removed providers — map to Puter (Settings is source of truth).
_LEGACY_IMAGE_PROVIDERS = frozenset({"bfl", "cloudflare", "pollinations", "nvidia", "flux"})


def build_image_provider():
    """Build image provider from Settings (tenant credentials), default Puter."""
    from initials_agent.tenant import cred_get, current_user_id, load_credentials

    settings = get_settings()
    uid = current_user_id()
    # Prefer per-account Settings credentials whenever present (SaaS + local)
    creds = load_credentials(uid) if uid else {}
    if creds.get("image_api_key") or creds.get("image_provider"):
        key = _clean_secret(str(creds.get("image_api_key") or ""))
        provider = _clean_secret(str(creds.get("image_provider") or "puter")).lower()
        model = _clean_secret(str(creds.get("image_model_name") or "")) or _clean_secret(
            settings.image.model_name
        )
    elif uid and uid != "local":
        key = cred_get("image_api_key")
        provider = (cred_get("image_provider") or "puter").lower()
        model = cred_get("image_model_name") or _clean_secret(settings.image.model_name)
    else:
        key = _clean_secret(settings.image.api_key.get_secret_value() if settings.image.api_key else "")
        provider = _clean_secret(settings.image.provider).lower() or "puter"
        model = _clean_secret(settings.image.model_name)

    if provider in _LEGACY_IMAGE_PROVIDERS:
        logger.warning(
            "Image provider %r is no longer supported — using puter. "
            "Add your Puter token in Settings (old key cleared).",
            provider,
        )
        provider = "puter"
        # BFL / Cloudflare keys are not Puter tokens
        key = ""

    if provider == "mock":
        return MockImageProvider()
    if not key:
        from initials_agent.providers.image.base import ImageProvider
        from initials_agent.providers.image.http_util import ImageProviderError

        class _MissingImageKeyProvider(ImageProvider):
            async def generate_image(self, concept):  # type: ignore[override]
                raise ImageProviderError(
                    "Puter token missing. Open Settings → Image generation and paste your Puter auth token."
                )

        logger.warning("No image API key in Settings — visual stage will fail until configured")
        return _MissingImageKeyProvider()
    if provider == "puter":
        return PuterImageProvider(key, model or "openai/gpt-image-2")
    if provider == "openrouter":
        return OpenRouterImageProvider(key, model)
    if provider == "dalle":
        return DalleImageProvider(key)
    if provider == "gemini":
        return GeminiImageProvider(key, model)
    logger.warning("Unknown image provider %r — using puter", provider)
    return PuterImageProvider(key, model or "openai/gpt-image-2")


def build_publishers(session):
    """Wire live LinkedIn / Instagram publishers when credentials exist."""
    from initials_agent.tenant import cred_get, current_user_id

    settings = get_settings()
    if current_user_id() and current_user_id() != "local":
        li_token = cred_get("linkedin_access_token")
        author = cred_get("linkedin_author_urn")
        ig_token = cred_get("instagram_access_token")
        ig_user = cred_get("instagram_account_id")
    else:
        li_token = _clean_secret(
            settings.linkedin.access_token.get_secret_value() if settings.linkedin.access_token else ""
        )
        author = _clean_secret(settings.linkedin.author_urn)
        ig_token = _clean_secret(
            settings.instagram.access_token.get_secret_value() if settings.instagram.access_token else ""
        )
        ig_user = _clean_secret(settings.instagram.account_id)

    if li_token and author:
        from initials_agent.services.publishing.linkedin import LinkedInPublisher

        logger.info("Using live LinkedIn publisher")
        linkedin = LinkedInPublisher(li_token, author)
    else:
        logger.info("LinkedIn not connected — using mock publisher")
        linkedin = MockSocialPublisher()

    if ig_token and ig_user:
        from initials_agent.services.publishing.instagram import InstagramPublisher

        logger.info("Using live Instagram publisher")
        instagram = InstagramPublisher(ig_token, ig_user)
    else:
        logger.info("Instagram not connected — using mock publisher")
        instagram = MockSocialPublisher()

    return PublishingService(linkedin, instagram, PublishingRepository(session))


def build_agent(session) -> DailyContentAgent:
    from initials_agent.tenant import tenant_images_dir

    llm = build_llm()
    img_prov = build_image_provider()
    img_srv = ImageGenerationService(img_prov, str(tenant_images_dir()))
    vis_srv = VisualContentService(llm, img_srv)
    return DailyContentAgent(
        research=build_research(),
        strategist=ContentStrategistService(TopicRepository(session)),
        writer=ContentWriterService(llm),
        visual=vis_srv,
        image_gen=img_srv,
        quality=QualityControlService(llm),
        approval=LocalApprovalService(ApprovalRepository(session)),
        publishing=build_publishers(session),
        analytics=AnalyticsService(
            MockAnalyticsProvider(),
            MockAnalyticsProvider(),
            AnalyticsRepository(session),
            llm,
        ),
        session=session,
    )


def default_topic(explicit: str | None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    from initials_agent.product.profile import load_profile

    return load_profile().research_query() or DAILY_TECH_QUERY

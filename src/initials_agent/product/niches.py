"""Market niche presets — category is set once in Settings and drives all generation."""

from __future__ import annotations

from dataclasses import dataclass

from initials_agent.daily import DAILY_TECH_QUERY


@dataclass(frozen=True)
class Niche:
    id: str
    label: str
    query: str
    # Strong terms that must appear for a story to count as this niche
    primary_terms: tuple[str, ...]
    # Optional niche-specific RSS feeds (Google News + vertical)
    feeds: tuple[str, ...] = ()


def _gnews(*parts: str) -> str:
    q = "+OR+".join(p.replace(" ", "+") for p in parts)
    return f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"


NICHES: list[Niche] = [
    Niche(
        "ai_automation",
        "AI & Automation",
        DAILY_TECH_QUERY,
        ("ai", "llm", "agent", "automation", "generative", "openai", "model"),
        (
            "https://hnrss.org/newest?q=AI+OR+LLM+OR+agent+OR+automation",
            "https://techcrunch.com/category/artificial-intelligence/feed/",
            "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
            _gnews("artificial intelligence", "LLM", "AI agent", "automation"),
        ),
    ),
    Niche(
        "saas_product",
        "SaaS & Product",
        "SaaS product management PLG growth B2B software startups pricing retention",
        ("saas", "product", "plg", "subscription", "b2b", "pricing", "retention"),
        (_gnews("SaaS", "product-led growth", "B2B software", "subscription software"),),
    ),
    Niche(
        "cybersecurity",
        "Cybersecurity",
        "cybersecurity zero trust ransomware cloud security identity breach infosec",
        ("cyber", "security", "ransomware", "breach", "infosec", "malware", "zero-trust", "zero trust"),
        (_gnews("cybersecurity", "ransomware", "data breach", "zero trust"),),
    ),
    Niche(
        "founders_startups",
        "Founders & Startups",
        "startup founders fundraising venture capital indie hackers bootstrap growth",
        ("startup", "founder", "venture", "fundraising", "seed", "series"),
        (_gnews("startup funding", "venture capital", "founders", "seed round"),),
    ),
    Niche(
        "enterprise_dx",
        "Enterprise / Digital Transformation",
        "enterprise digital transformation cloud migration automation ERP operations",
        ("enterprise", "transformation", "erp", "migration", "operations", "digital"),
        (_gnews("digital transformation", "enterprise software", "ERP", "cloud migration"),),
    ),
    Niche(
        "marketing_growth",
        "Marketing & Growth",
        "growth marketing demand generation SEO content marketing attribution CRO",
        ("marketing", "seo", "growth", "attribution", "cro", "demand"),
        (_gnews("growth marketing", "SEO", "demand generation", "content marketing"),),
    ),
    Niche(
        "fintech",
        "Fintech",
        "fintech payments banking neobank lending compliance open banking embedded finance",
        ("fintech", "payment", "banking", "neobank", "lending", "finance"),
        (_gnews("fintech", "digital banking", "payments", "neobank"),),
    ),
    Niche(
        "ecommerce",
        "E-commerce & Retail tech",
        "ecommerce retail DTC marketplace logistics conversion checkout merchandising",
        ("ecommerce", "e-commerce", "retail", "dtc", "marketplace", "checkout"),
        (_gnews("ecommerce", "retail tech", "DTC", "online marketplace"),),
    ),
    Niche(
        "healthtech",
        "Healthtech",
        "healthtech digital health telemedicine EHR clinical AI medtech patient care hospital",
        ("health", "healthcare", "medical", "clinical", "patient", "telemedicine", "ehr", "medtech", "hospital", "pharma"),
        (
            _gnews("healthtech", "digital health", "telemedicine", "EHR", "medtech"),
            "https://techcrunch.com/tag/health/feed/",
        ),
    ),
    Niche(
        "custom",
        "Custom…",
        "",
        (),
        (),
    ),
]

NICHE_BY_ID = {n.id: n for n in NICHES}

# Broad fallback feeds when a niche has none
DEFAULT_FEEDS = (
    "https://techcrunch.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
    "https://www.theverge.com/rss/index.xml",
    "https://hnrss.org/newest",
)


def niche_labels() -> list[str]:
    return [n.label for n in NICHES]


def niche_id_for_label(label: str) -> str:
    for n in NICHES:
        if n.label == label:
            return n.id
    return "ai_automation"


def resolve_research_query(niche_id: str, custom_text: str | None = None) -> str:
    niche = NICHE_BY_ID.get(niche_id) or NICHE_BY_ID["ai_automation"]
    if niche.id == "custom":
        text = (custom_text or "").strip()
        return text or DAILY_TECH_QUERY
    return niche.query


def resolve_primary_terms(niche_id: str, custom_text: str | None = None) -> list[str]:
    niche = NICHE_BY_ID.get(niche_id) or NICHE_BY_ID["ai_automation"]
    if niche.id == "custom":
        return [t.lower() for t in (custom_text or "").replace(",", " ").split() if len(t) > 2]
    return list(niche.primary_terms)


def resolve_feeds(niche_id: str, custom_text: str | None = None) -> tuple[str, ...]:
    niche = NICHE_BY_ID.get(niche_id) or NICHE_BY_ID["ai_automation"]
    if niche.id == "custom":
        text = (custom_text or "").strip()
        if text:
            return (_gnews(*text.split()[:6]),) + DEFAULT_FEEDS
        return DEFAULT_FEEDS
    return niche.feeds + DEFAULT_FEEDS

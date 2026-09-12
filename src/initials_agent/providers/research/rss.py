import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import httpx

from initials_agent.product.niches import DEFAULT_FEEDS, resolve_feeds, resolve_primary_terms
from initials_agent.providers.research.base import RawSearchResult, ResearchProvider
from initials_agent.providers.research.mock import MockResearchProvider

logger = logging.getLogger(__name__)

DOMAIN_CREDIBILITY = {
    "techcrunch.com": 0.92,
    "arstechnica.com": 0.9,
    "theverge.com": 0.82,
    "wired.com": 0.88,
    "news.ycombinator.com": 0.84,
    "hnrss.org": 0.8,
    "news.google.com": 0.75,
}

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "dc": "http://purl.org/dc/elements/1.1/",
    "content": "http://purl.org/rss/1.0/modules/content/",
}


def _text(el: ET.Element | None) -> str:
    if el is None or el.text is None:
        return ""
    return " ".join(el.text.split())


def _parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except Exception:
        return None


def parse_feed(xml_text: str, fallback_domain: str) -> list[RawSearchResult]:
    root = ET.fromstring(xml_text)
    items: list[RawSearchResult] = []

    rss_items = root.findall("./channel/item")
    atom_entries = root.findall("atom:entry", NS) if not rss_items else []

    if rss_items:
        for item in rss_items:
            title = _text(item.find("title"))
            link = _text(item.find("link"))
            summary = _text(item.find("description")) or _text(item.find("content:encoded", NS))
            published = _parse_date(_text(item.find("pubDate")) or _text(item.find("dc:date", NS)))
            if not title or not link:
                continue
            domain = urlparse(link).netloc.replace("www.", "") or fallback_domain
            items.append(
                RawSearchResult(
                    title=title,
                    url=link,
                    summary=summary[:400] or title,
                    published_date=published or datetime.now(UTC),
                    source_domain=domain,
                )
            )
        return items

    for entry in atom_entries:
        title = _text(entry.find("atom:title", NS))
        link_el = entry.find("atom:link", NS)
        link = (link_el.get("href") if link_el is not None else "") or _text(entry.find("atom:id", NS))
        summary = _text(entry.find("atom:summary", NS)) or _text(entry.find("atom:content", NS))
        published = _parse_date(_text(entry.find("atom:updated", NS)) or _text(entry.find("atom:published", NS)))
        if not title or not link:
            continue
        domain = urlparse(link).netloc.replace("www.", "") or fallback_domain
        items.append(
            RawSearchResult(
                title=title,
                url=link,
                summary=summary[:400] or title,
                published_date=published or datetime.now(UTC),
                source_domain=domain,
            )
        )
    return items


def _niche_score(item: RawSearchResult, primary_terms: list[str], query: str) -> float:
    hay = f"{item.title} {item.summary}".lower()
    if not primary_terms:
        terms = [t.lower() for t in query.replace(",", " ").split() if len(t) > 2]
        return float(sum(1 for t in terms if t in hay))
    hits = sum(1 for t in primary_terms if t in hay)
    return float(hits)


class RssResearchProvider(ResearchProvider):
    """Pulls live headlines and keeps only stories matching the Settings category."""

    def __init__(self, feeds: tuple[str, ...] | None = None, niche_id: str | None = None):
        self.feeds = feeds
        self.niche_id = niche_id

    async def search(self, query: str, limit: int = 5) -> list[RawSearchResult]:
        from initials_agent.product.profile import load_profile

        profile = load_profile()
        niche_id = self.niche_id or profile.active_niche_id
        custom = profile.custom_niche_text if niche_id == "custom" else ""
        feeds = self.feeds or resolve_feeds(niche_id, custom)
        primary = resolve_primary_terms(niche_id, custom)

        collected: list[RawSearchResult] = []
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
            for feed in feeds:
                try:
                    response = await client.get(
                        feed, headers={"User-Agent": "DailyContentAgent/1.0"}
                    )
                    response.raise_for_status()
                    domain = urlparse(feed).netloc
                    collected.extend(parse_feed(response.text, domain))
                except Exception as exc:
                    logger.warning("RSS feed failed (%s): %s", feed, exc)

        if not collected:
            logger.warning("All RSS feeds failed; using mock research fallback.")
            return await MockResearchProvider().search(query, limit=limit)

        scored: list[tuple[float, RawSearchResult]] = []
        for item in collected:
            score = _niche_score(item, primary, query)
            if score <= 0:
                continue
            scored.append((score, item))
        scored.sort(key=lambda pair: pair[0], reverse=True)

        # Strict: only niche-matching stories. Never fall back to unrelated headlines.
        if not scored:
            logger.warning(
                "No headlines matched niche=%s; refusing off-topic fallback.", niche_id
            )
            # Last resort: niche-shaped mock so the pipeline can still write on-brand
            return await MockResearchProvider().search(query, limit=limit)

        seen: set[str] = set()
        unique: list[RawSearchResult] = []
        for _score, item in scored:
            key = str(item.url)
            if key in seen:
                continue
            seen.add(key)
            unique.append(item)
            if len(unique) >= max(limit, 8):
                break
        return unique[: max(limit, 5)]

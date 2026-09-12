"""Customer brand + automation profile for the sellable desktop agent."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

from initials_agent.product.niches import NICHE_BY_ID, resolve_research_query

PublishMode = Literal["review", "auto_linkedin", "auto_instagram", "auto_both"]


def platforms_for_mode(mode: str) -> list[str]:
    if mode == "auto_linkedin":
        return ["linkedin"]
    if mode == "auto_instagram":
        return ["instagram"]
    if mode == "auto_both":
        return ["linkedin", "instagram"]
    return []


def is_auto_publish(mode: str) -> bool:
    return mode in ("auto_linkedin", "auto_instagram", "auto_both")


def profile_path() -> Path:
    """Per-auth-user profile (falls back to local workspace when no tenant)."""
    from initials_agent.tenant import profile_path as tenant_profile_path

    return tenant_profile_path()


class BrandProfile(BaseModel):
    business_name: str = ""
    positioning: str = ""
    audience: str = "Founders, operators, and buyers in our market"
    voice_notes: str = "Confident, practical, clear. No hype."
    # What we promote when newsjacking external articles
    offer: str = ""
    proof_points: str = ""
    cta_text: str = "Book a demo"
    website_url: str = ""
    active_niche_id: str = "ai_automation"
    custom_niche_text: str = ""
    enabled_niche_ids: list[str] = Field(
        default_factory=lambda: [
            "ai_automation",
            "saas_product",
            "cybersecurity",
            "founders_startups",
            "enterprise_dx",
            "marketing_growth",
            "fintech",
            "ecommerce",
            "healthtech",
            "custom",
        ]
    )
    schedule_enabled: bool = False
    schedule_time: str = "09:00"
    timezone: str = "Asia/Kolkata"
    publish_mode: PublishMode = "review"
    setup_complete: bool = False

    def is_ready(self) -> bool:
        return bool(self.business_name.strip() and self.positioning.strip() and self.setup_complete)

    def niche_label(self) -> str:
        niche = NICHE_BY_ID.get(self.active_niche_id)
        if self.active_niche_id == "custom" and self.custom_niche_text.strip():
            return f"Custom: {self.custom_niche_text.strip()[:48]}"
        return niche.label if niche else "AI & Automation"

    def research_query(self) -> str:
        return resolve_research_query(self.active_niche_id, self.custom_niche_text)

    def brand_config(self) -> dict[str, str]:
        name = self.business_name.strip() or "Your Brand"
        positioning = self.positioning.strip() or (
            "Help customers solve real problems with clear, practical content."
        )
        offer = self.offer.strip() or positioning
        return {
            "name": name,
            "positioning": positioning,
            "audience": self.audience.strip() or "Business professionals",
            "voice": self.voice_notes.strip() or "Confident, practical, clear",
            "niche_label": self.niche_label(),
            "offer": offer,
            "proof_points": self.proof_points.strip(),
            "cta_text": self.cta_text.strip() or "Book a demo",
            "website_url": self.website_url.strip(),
        }


def load_profile() -> BrandProfile:
    path = profile_path()
    if not path.exists():
        return BrandProfile()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return BrandProfile.model_validate(data)
    except Exception:
        return BrandProfile()


def save_profile(profile: BrandProfile) -> BrandProfile:
    path = profile_path()
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return profile


def update_profile(**kwargs: Any) -> BrandProfile:
    profile = load_profile()
    data = profile.model_dump()
    data.update({k: v for k, v in kwargs.items() if v is not None})
    updated = BrandProfile.model_validate(data)
    return save_profile(updated)

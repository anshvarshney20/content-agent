import io
import logging
import os
import uuid

from PIL import Image
from tenacity import retry, stop_after_attempt, wait_exponential

from initials_agent.config import get_settings
from initials_agent.models.content import GeneratedAsset, VisualConcept
from initials_agent.providers.image.base import ImageProvider

logger = logging.getLogger(__name__)


class ImageGenerationService:
    def __init__(self, provider: ImageProvider, output_dir: str):
        self.provider = provider
        self.output_dir = output_dir
        # Local dir only used if Supabase is not configured (legacy desktop)
        os.makedirs(self.output_dir, exist_ok=True)

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8))
    async def _generate_with_retry(self, concept: VisualConcept) -> bytes:
        return await self.provider.generate_image(concept)

    async def generate(
        self,
        draft_id: uuid.UUID,
        concept: VisualConcept,
        *,
        asset_type: str = "image",
    ) -> GeneratedAsset:
        try:
            image_bytes = await self._generate_with_retry(concept)
        except Exception as e:
            logger.error("Image generation failed: %s", e)
            raise ValueError(f"Provider error: {e!s}") from e

        try:
            img = Image.open(io.BytesIO(image_bytes))
            img.verify()
            img = Image.open(io.BytesIO(image_bytes))
        except Exception as e:
            raise ValueError("Invalid image returned by provider.") from e

        fmt = (img.format or "PNG").upper()
        fmt_l = fmt.lower()
        if fmt_l not in ["jpeg", "jpg", "png", "webp"]:
            raise ValueError(f"Unsupported MIME format: {fmt_l}")

        width, height = img.size
        if width < 100 or height < 100:
            raise ValueError(f"Image dimensions too small: {width}x{height}")

        # Strip EXIF into clean buffer (no disk)
        data = list(img.getdata())
        safe_img = Image.new(img.mode, img.size)
        safe_img.putdata(data)
        buf = io.BytesIO()
        if fmt_l == "png":
            from PIL import PngImagePlugin

            pnginfo = PngImagePlugin.PngInfo()
            pnginfo.add_text("headline", concept.headline[:50])
            pnginfo.add_text("subject", concept.visual_subject[:50])
            safe_img.save(buf, format="PNG", pnginfo=pnginfo)
            content_type = "image/png"
            ext = "png"
        elif fmt_l in ("jpeg", "jpg"):
            if safe_img.mode in ("RGBA", "P"):
                safe_img = safe_img.convert("RGB")
            safe_img.save(buf, format="JPEG", quality=92)
            content_type = "image/jpeg"
            ext = "jpg"
        else:
            safe_img.save(buf, format="WEBP", quality=90)
            content_type = "image/webp"
            ext = "webp"

        payload = buf.getvalue()
        filename = f"{draft_id}_{asset_type}.{ext}".replace(" ", "_")

        from initials_agent.saas.supabase_client import supabase_configured, upload_image_bytes
        from initials_agent.saas.sync import resolve_brand_id

        settings = get_settings()
        if supabase_configured():
            brand_id = await resolve_brand_id(
                getattr(settings, "_brand_name_hint", None)
                or None
            )
            # Prefer profile business name
            try:
                from initials_agent.product.profile import load_profile

                brand_id = await resolve_brand_id(load_profile().business_name) or brand_id
            except Exception:
                pass
            if not brand_id:
                raise RuntimeError(
                    "Supabase is configured but no brand exists. "
                    "Sign up once in the React app, then Generate again."
                )
            public_url = await upload_image_bytes(
                brand_id, filename, payload, content_type=content_type
            )
            logger.info("Image stored on Supabase only: %s", public_url)
            return GeneratedAsset(url=public_url, asset_type=asset_type or "image")

        # Legacy local path — only when Supabase keys are missing
        if settings.saas.enabled:
            raise RuntimeError(
                "SAAS__ENABLED requires Supabase image storage. Set SUPABASE__URL and SERVICE_ROLE_KEY."
            )
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "wb") as f:
            f.write(payload)
        logger.warning("Supabase not configured — saved image locally (legacy): %s", filepath)
        return GeneratedAsset(url=filepath, asset_type=asset_type or "image")

import asyncio
import json
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from initials_agent.models.content import VisualConcept
from initials_agent.providers.image.base import ImageProvider
from initials_agent.providers.image.http_util import ImageProviderError

logger = logging.getLogger(__name__)

DEFAULT_PUTER_MODEL = "openai/gpt-image-2"
BRIDGE_DIR = Path(__file__).resolve().parents[4] / "scripts" / "puter"
BRIDGE_SCRIPT = BRIDGE_DIR / "txt2img.mjs"


def _run_puter_bridge(
    *,
    node: str,
    bridge_script: Path,
    prompt: str,
    model_name: str,
    quality: str,
    auth_token: str,
    out_path: Path,
) -> tuple[int, str, str]:
    """Sync Node bridge — safe on Windows under uvicorn (no asyncio subprocess)."""
    env = os.environ.copy()
    env["PUTER_AUTH_TOKEN"] = auth_token
    completed = subprocess.run(
        [
            node,
            str(bridge_script),
            "--prompt",
            prompt,
            "--model",
            model_name,
            "--quality",
            quality,
            "--out",
            str(out_path),
        ],
        cwd=str(bridge_script.parent),
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    return completed.returncode, completed.stdout or "", completed.stderr or ""


class PuterImageProvider(ImageProvider):
    """Generate images through Puter.js (user-pays) via a Node bridge."""

    def __init__(
        self,
        auth_token: str,
        model_name: str = DEFAULT_PUTER_MODEL,
        quality: str = "low",
        bridge_script: Path | None = None,
    ):
        if not auth_token:
            raise ValueError("Puter auth token is required (IMAGE__API_KEY / PUTER_AUTH_TOKEN)")
        self.auth_token = auth_token.strip()
        self.model_name = (model_name or DEFAULT_PUTER_MODEL).strip()
        self.quality = quality or "low"
        self.bridge_script = Path(bridge_script) if bridge_script else BRIDGE_SCRIPT

    async def generate_image(self, concept: VisualConcept) -> bytes:
        prompt = concept.visual_subject
        if concept.headline and concept.headline != "CLI Prompt":
            prompt = (
                f"Headline: {concept.headline}. Subject: {concept.visual_subject}. "
                f"Style: {concept.composition}, {concept.environment}, {concept.lighting}."
            )

        node = shutil.which("node")
        if not node:
            raise ImageProviderError(
                "Node.js is required for Puter image generation. Install Node, then retry."
            )
        if not self.bridge_script.exists():
            raise ImageProviderError(f"Puter bridge missing: {self.bridge_script}")

        with tempfile.TemporaryDirectory(prefix="puter_img_") as tmp:
            out_path = Path(tmp) / "out.png"
            try:
                returncode, raw, err_text = await asyncio.to_thread(
                    _run_puter_bridge,
                    node=node,
                    bridge_script=self.bridge_script,
                    prompt=prompt,
                    model_name=self.model_name,
                    quality=self.quality,
                    auth_token=self.auth_token,
                    out_path=out_path,
                )
            except subprocess.TimeoutExpired as exc:
                raise ImageProviderError(
                    "Puter image generation timed out after 180s. "
                    "Retry Generate, or set IMAGE__PROVIDER=mock."
                ) from exc

            payload = None
            for line in reversed((raw or "").splitlines() or [""]):
                line = line.strip()
                if line.startswith("{") and line.endswith("}"):
                    try:
                        payload = json.loads(line)
                        break
                    except json.JSONDecodeError:
                        continue

            if returncode != 0 or not payload or not payload.get("ok"):
                detail = (payload or {}).get("error") if isinstance(payload, dict) else None
                detail = detail or err_text or raw or f"exit {returncode}"
                raise ImageProviderError(f"Puter image generation failed: {detail}")

            if not out_path.exists():
                raise ImageProviderError(
                    "Puter bridge reported success but no image file was written."
                )
            data = out_path.read_bytes()
            if len(data) < 32:
                raise ImageProviderError("Puter returned an empty or invalid image.")
            logger.info("Puter generated %s bytes via %s", len(data), self.model_name)
            return data

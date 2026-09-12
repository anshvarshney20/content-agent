import json
from pathlib import Path

import pytest

from initials_agent.models.content import VisualConcept
from initials_agent.providers.image.http_util import ImageProviderError
from initials_agent.providers.image.puter import PuterImageProvider


def _concept() -> VisualConcept:
    return VisualConcept(
        aspect_ratio="1:1",
        composition="minimal",
        headline="CLI Prompt",
        supporting_text="",
        visual_subject="Futuristic city with flying cars",
        environment="studio",
        lighting="cinematic",
        color_palette="dark",
        typography="none",
        negative_prompt="",
        brand_requirements="INITΛLS",
    )


@pytest.mark.asyncio
async def test_puter_success(monkeypatch, tmp_path):
    script = tmp_path / "txt2img.mjs"
    script.write_text("// stub", encoding="utf-8")
    png = b"\x89PNG\r\n\x1a\n" + b"x" * 40

    class FakeProc:
        def __init__(self):
            self.returncode = 0

        async def communicate(self):
            # Provider writes --out path; we can't know it from here easily.
            # Instead monkeypatch the whole subprocess to write via side channel.
            return (
                json.dumps({"ok": True, "path": "out.png", "bytes": len(png)}).encode(),
                b"",
            )

    async def fake_exec(*args, **kwargs):
        # Find --out path and write bytes
        argv = list(args)
        out_idx = argv.index("--out")
        out_path = Path(argv[out_idx + 1])
        out_path.write_bytes(png)
        return FakeProc()

    monkeypatch.setattr("initials_agent.providers.image.puter.shutil.which", lambda _: "node")
    monkeypatch.setattr("initials_agent.providers.image.puter.asyncio.create_subprocess_exec", fake_exec)

    provider = PuterImageProvider("token", "openai/gpt-image-2", bridge_script=script)
    data = await provider.generate_image(_concept())
    assert data.startswith(b"\x89PNG")


@pytest.mark.asyncio
async def test_puter_missing_node(monkeypatch, tmp_path):
    script = tmp_path / "txt2img.mjs"
    script.write_text("// stub", encoding="utf-8")
    monkeypatch.setattr("initials_agent.providers.image.puter.shutil.which", lambda _: None)
    provider = PuterImageProvider("token", bridge_script=script)
    with pytest.raises(ImageProviderError, match="Node.js"):
        await provider.generate_image(_concept())


@pytest.mark.asyncio
async def test_puter_bridge_error(monkeypatch, tmp_path):
    script = tmp_path / "txt2img.mjs"
    script.write_text("// stub", encoding="utf-8")

    class FakeProc:
        returncode = 1

        async def communicate(self):
            return (json.dumps({"ok": False, "error": "auth failed"}).encode(), b"")

    async def fake_exec(*args, **kwargs):
        return FakeProc()

    monkeypatch.setattr("initials_agent.providers.image.puter.shutil.which", lambda _: "node")
    monkeypatch.setattr("initials_agent.providers.image.puter.asyncio.create_subprocess_exec", fake_exec)
    provider = PuterImageProvider("token", bridge_script=script)
    with pytest.raises(ImageProviderError, match="auth failed"):
        await provider.generate_image(_concept())


def test_build_image_provider_puter(monkeypatch):
    from initials_agent.config import ImageGenerationConfig, Settings
    from initials_agent import runtime

    def mock_settings():
        s = Settings()
        s.image = ImageGenerationConfig(
            provider="puter",
            api_key="puter-token",
            model_name="google/gemini-3-pro-image-preview",
        )
        return s

    monkeypatch.setattr(runtime, "get_settings", mock_settings)
    prov = runtime.build_image_provider()
    assert isinstance(prov, PuterImageProvider)
    assert prov.model_name == "google/gemini-3-pro-image-preview"

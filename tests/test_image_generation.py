import pytest
import os
import uuid
import shutil
from initials_agent.models.content import VisualConcept
from initials_agent.services.image_generation.service import ImageGenerationService
from initials_agent.providers.image.mock import MockImageProvider
from initials_agent.providers.image.base import ImageProvider

@pytest.fixture
def output_dir():
    path = os.path.join(os.getcwd(), "test_images_output")
    os.makedirs(path, exist_ok=True)
    yield path
    shutil.rmtree(path)

@pytest.fixture
def concept():
    return VisualConcept(
        aspect_ratio="1:1",
        composition="Test",
        headline="Test Headline",
        supporting_text="Test Sub",
        visual_subject="A robot",
        environment="Space",
        lighting="Neon",
        color_palette="Blue",
        typography="Sans",
        negative_prompt="Ugly",
        brand_requirements="Clean"
    )

@pytest.mark.asyncio
async def test_image_generation_success(output_dir, concept):
    provider = MockImageProvider()
    service = ImageGenerationService(provider, output_dir)
    draft_id = uuid.uuid4()
    
    asset = await service.generate(draft_id, concept)
    
    assert asset.asset_type == "image"
    assert asset.url.endswith(".png")
    assert os.path.exists(asset.url)
    
    # Check if file has metadata
    from PIL import Image
    img = Image.open(asset.url)
    assert img.text["headline"] == "Test Headline"
    assert img.text["subject"] == "A robot"
    assert img.size == (150, 150)

@pytest.mark.asyncio
async def test_image_generation_invalid_dimensions(output_dir, concept):
    class BadProvider(ImageProvider):
        async def generate_image(self, concept):
            from PIL import Image
            import io
            # Return a 1x1 image
            img = Image.new("RGB", (1, 1), color="red")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
            
    provider = BadProvider()
    service = ImageGenerationService(provider, output_dir)
    
    with pytest.raises(ValueError, match="Image dimensions too small"):
        await service.generate(uuid.uuid4(), concept)
        
@pytest.mark.asyncio
async def test_image_generation_provider_error(output_dir, concept):
    class ErrorProvider(ImageProvider):
        async def generate_image(self, concept):
            raise ConnectionError("API is down")
            
    provider = ErrorProvider()
    # Mock tenacity retry configuration to be very fast for test
    service = ImageGenerationService(provider, output_dir)
    service._generate_with_retry.retry.wait.multiplier = 0.01 # type: ignore
    
    with pytest.raises(ValueError, match="Provider error:"):
        await service.generate(uuid.uuid4(), concept)

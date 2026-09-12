import pytest
from fastapi.testclient import TestClient
from initials_agent.api.main import app, VISUAL_JOBS
from initials_agent.db.models import StandaloneVisualModel, ContentDraftModel, Base
from initials_agent.db.session import get_engine, get_session_factory

client = TestClient(app)

def test_generate_visual_provider_not_configured(monkeypatch):
    from initials_agent.config import Settings, ImageGenerationConfig
    
    def mock_settings():
        s = Settings()
        s.image = ImageGenerationConfig(provider="dalle", api_key=None)
        return s
        
    monkeypatch.setattr("initials_agent.api.main.get_settings", mock_settings)
    
    res = client.post("/api/visuals/generate", json={
        "topic": "Test Topic",
        "prompt": "Test Prompt",
        "platform": "instagram",
        "aspect_ratio": "4:5"
    })
    assert res.status_code == 200
    job_id = res.json()["job_id"]
    
    # Wait for job to process
    import time
    time.sleep(0.5)
    
    job_res = client.get(f"/api/visuals/jobs/{job_id}")
    assert job_res.status_code == 200
    assert job_res.json()["status"] == "Failed"
    assert "not configured" in job_res.json()["error"]

def test_generate_visual_success(monkeypatch):
    from initials_agent.config import Settings, ImageGenerationConfig
    import os
    
    def mock_settings():
        s = Settings()
        s.image = ImageGenerationConfig(provider="dalle", api_key="test-key")
        return s
        
    class MockProvider:
        def __init__(self, key):
            pass
        async def generate_image(self, concept):
            return b"fake image"
            
    monkeypatch.setattr("initials_agent.api.main.get_settings", mock_settings)
    monkeypatch.setattr("initials_agent.providers.image.dalle.DalleImageProvider", MockProvider)
    
    res = client.post("/api/visuals/generate", json={
        "topic": "Test Topic Success",
        "prompt": "Test Prompt Success",
        "platform": "instagram",
        "aspect_ratio": "4:5"
    })
    job_id = res.json()["job_id"]
    
    import time
    time.sleep(0.5)
    
    job_res = client.get(f"/api/visuals/jobs/{job_id}")
    assert job_res.json()["status"] == "Completed"
    assert job_res.json()["result"]["provider"] == "Dalle"
    assert "/images/gen_" in job_res.json()["result"]["image_url"]
    
    # Cleanup
    if os.path.exists("test_output.png"):
        os.remove("test_output.png")

def test_generate_visual_provider_failure(monkeypatch):
    from initials_agent.config import Settings, ImageGenerationConfig
    
    def mock_settings():
        s = Settings()
        s.image = ImageGenerationConfig(provider="dalle", api_key="test-key")
        return s
        
    class MockProviderError:
        def __init__(self, key):
            pass
        async def generate_image(self, concept):
            raise Exception("API Rate Limit")
            
    monkeypatch.setattr("initials_agent.api.main.get_settings", mock_settings)
    monkeypatch.setattr("initials_agent.providers.image.dalle.DalleImageProvider", MockProviderError)
    
    res = client.post("/api/visuals/generate", json={
        "topic": "Test Error",
        "prompt": "Test Error",
        "platform": "instagram",
        "aspect_ratio": "4:5"
    })
    job_id = res.json()["job_id"]
    
    import time
    time.sleep(0.5)
    
    job_res = client.get(f"/api/visuals/jobs/{job_id}")
    assert job_res.json()["status"] == "Failed"
    assert "API Rate Limit" in job_res.json()["error"]

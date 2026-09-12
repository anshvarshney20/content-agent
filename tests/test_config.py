import os
import pytest
from pydantic import ValidationError
from initials_agent.config import get_settings, Settings

def test_config_defaults():
    settings = get_settings()
    assert settings.app.name == "Daily Content Agent"
    assert settings.app.environment == "development"
    assert settings.app.log_level == "INFO"
    assert settings.ai.provider == "openrouter"
    assert settings.ai.model_name == "deepseek/deepseek-v4-flash-0731"

def test_production_config_validation(monkeypatch):
    # Simulate missing API key in production
    monkeypatch.setenv("APP__ENVIRONMENT", "production")
    with pytest.raises(ValidationError) as exc_info:
        Settings()
    assert "AI provider API key is required in production environment" in str(exc_info.value)

def test_production_config_success(monkeypatch):
    monkeypatch.setenv("APP__ENVIRONMENT", "production")
    monkeypatch.setenv("AI__API_KEY", "test-secret-key")
    settings = Settings()
    assert settings.app.environment == "production"
    assert settings.ai.api_key.get_secret_value() == "test-secret-key"

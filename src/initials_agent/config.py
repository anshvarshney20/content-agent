
from pydantic import BaseModel, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppConfig(BaseModel):
    name: str = "Daily Content Agent"
    environment: str = "development"
    log_level: str = "INFO"
    # Public HTTPS base (e.g. ngrok) so Instagram can fetch /images/*.png
    public_base_url: str | None = None

class AIProviderConfig(BaseModel):
    provider: str = "openrouter"
    api_key: SecretStr | None = None
    model_name: str = "deepseek/deepseek-v4-flash-0731"

class ResearchConfig(BaseModel):
    max_sources: int = 5
    search_api_key: SecretStr | None = None

class ImageGenerationConfig(BaseModel):
    provider: str = "puter"
    api_key: SecretStr | None = None
    resolution: str = "1024x1024"
    model_name: str = "openai/gpt-image-2"

class LinkedInConfig(BaseModel):
    client_id: str | None = None
    client_secret: SecretStr | None = None
    access_token: SecretStr | None = None
    author_urn: str | None = None  # e.g. urn:li:person:XXXX or urn:li:organization:XXXX

class InstagramConfig(BaseModel):
    account_id: str | None = None
    access_token: SecretStr | None = None
    # Facebook Place / location page ID for geotagging posts (optional)
    location_id: str | None = None
    location_name: str | None = None
    # Feed posts as swipeable carousels (2–7 slides; Graph API max 10)
    carousel_slides: int = 1

class DatabaseConfig(BaseModel):
    connection_string: str = "sqlite:///local.db"


class SupabaseConfig(BaseModel):
    url: str | None = None
    anon_key: SecretStr | None = None
    service_role_key: SecretStr | None = None
    storage_bucket: str = "post-images"


class SaasConfig(BaseModel):
    """Web/SaaS mode settings (Render + React + Supabase)."""

    enabled: bool = False
    cron_secret: SecretStr | None = None
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # Comma-separated emails allowed to use /api/admin/* (fail closed if empty)
    admin_emails: str = ""


class NotificationsConfig(BaseModel):
    slack_webhook_url: str | None = None

class SchedulingConfig(BaseModel):
    timezone: str = "Asia/Kolkata"
    publish_time: str = "09:00"

class Settings(BaseSettings):
    app: AppConfig = Field(default_factory=AppConfig)
    ai: AIProviderConfig = Field(default_factory=AIProviderConfig)
    research: ResearchConfig = Field(default_factory=ResearchConfig)
    image: ImageGenerationConfig = Field(default_factory=ImageGenerationConfig)
    linkedin: LinkedInConfig = Field(default_factory=LinkedInConfig)
    instagram: InstagramConfig = Field(default_factory=InstagramConfig)
    db: DatabaseConfig = Field(default_factory=DatabaseConfig)
    supabase: SupabaseConfig = Field(default_factory=SupabaseConfig)
    saas: SaasConfig = Field(default_factory=SaasConfig)
    notifications: NotificationsConfig = Field(default_factory=NotificationsConfig)
    scheduling: SchedulingConfig = Field(default_factory=SchedulingConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="ignore"
    )

    @model_validator(mode='after')
    def validate_production_config(self) -> 'Settings':
        if self.app.environment.lower() == 'production':
            if not self.ai.api_key:
                raise ValueError("AI provider API key is required in production environment.")
        return self

def get_settings() -> Settings:
    return Settings()

"""
Configuration management for UGA Course Scheduler.

Supports environment variables and .env files.
"""
import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "UGA Course Scheduler"
    app_version: str = "0.1.0"
    debug: bool = False

    # Database
    database_url: str = "postgresql://postgres:postgres@localhost:5432/uga_courses"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # For async operations
    @property
    def async_database_url(self) -> str:
        """Convert sync URL to async URL."""
        url = self.database_url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Vector/Embeddings
    embedding_provider: str = "voyage"  # "voyage" or "openai"
    embedding_model: str = "voyage-3-lite"  # voyage-3-lite (512d) or voyage-3 (1024d)
    embedding_dimensions: int = 512  # Dimensions for voyage-3-lite
    voyage_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None

    # Anthropic (for AI features)
    anthropic_api_key: Optional[str] = None

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: list[str] = ["*"]

    # Monitoring
    schedule_check_interval: int = 3600  # seconds

    # Firecrawl (for bulletin scraping)
    firecrawl_api_key: Optional[str] = None

    # Auth (Clerk)
    clerk_secret_key: Optional[str] = None
    clerk_publishable_key: Optional[str] = None
    clerk_webhook_secret: Optional[str] = None

    # Payments (Stripe)
    stripe_secret_key: Optional[str] = None
    stripe_publishable_key: Optional[str] = None
    stripe_webhook_secret: Optional[str] = None

    # Stripe Price IDs (set these after creating products in Stripe Dashboard)
    stripe_price_quarter: Optional[str] = None  # $9.99/quarter
    stripe_price_year: Optional[str] = None  # $24.99/year
    stripe_price_graduation: Optional[str] = None  # $199 one-time

    # Frontend URL for redirects
    frontend_url: str = "http://localhost:5173"

    # Notifications
    slack_webhook_url: Optional[str] = None


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Convenience access
settings = get_settings()

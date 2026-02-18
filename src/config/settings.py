"""
Configuration settings for ElvAgent using Pydantic Settings.
Loads configuration from environment variables with type validation.
"""

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Compute project root once (used for .env path)
_PROJECT_ROOT = Path(__file__).parent.parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),  # Absolute path to .env
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Project paths
    project_root: Path = Field(default=_PROJECT_ROOT)

    # Claude API
    anthropic_api_key: str | None = Field(
        default=None, description="Anthropic API key for Claude (required for production)"
    )
    anthropic_model: str = Field(
        default="claude-sonnet-4-5-20250929", description="Default Claude model to use"
    )

    # Social Media - Discord
    discord_webhook_url: str | None = Field(None, description="Discord webhook URL")

    # Social Media - Twitter
    twitter_api_key: str | None = None
    twitter_api_secret: str | None = None
    twitter_access_token: str | None = None
    twitter_access_secret: str | None = None

    # Social Media - Instagram
    instagram_access_token: str | None = None
    instagram_business_account_id: str | None = None

    # Social Media - Telegram
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    # Image Generation
    openai_api_key: str | None = Field(None, description="OpenAI API key for DALL-E")

    # Content Sources
    crunchbase_api_key: str | None = Field(None, description="Crunchbase API key (optional)")

    # Database
    database_path: Path = Field(
        default_factory=lambda: Path("/home/elvern/ElvAgent/data/state.db"),
        description="Path to SQLite database",
    )

    # Cost limits
    max_daily_cost: float = Field(default=5.0, description="Maximum daily API cost in USD")

    # Content Enhancement
    enable_content_enhancement: bool = Field(
        default=True, description="Enable AI content enhancement (adds ~$0.035 per newsletter)"
    )
    max_items_per_category: int = Field(
        default=5, description="Maximum items per category in enhanced mode"
    )

    # Logging
    log_level: str = Field(default="INFO", description="Logging level")

    @field_validator("database_path", mode="before")
    @classmethod
    def ensure_absolute_path(cls, v):
        """Ensure database path is absolute."""
        if isinstance(v, str):
            v = Path(v)
        if not v.is_absolute():
            return Path.cwd() / v
        return v

    @property
    def data_dir(self) -> Path:
        """Get data directory path."""
        return self.project_root / "data"

    @property
    def newsletters_dir(self) -> Path:
        """Get newsletters directory path."""
        return self.data_dir / "newsletters"

    @property
    def images_dir(self) -> Path:
        """Get images directory path."""
        return self.data_dir / "images"

    @property
    def logs_dir(self) -> Path:
        """Get logs directory path."""
        return self.project_root / "logs"

    def ensure_directories(self):
        """Create necessary directories if they don't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.newsletters_dir.mkdir(parents=True, exist_ok=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    def validate_production_config(self) -> bool:
        """
        Validate that required configuration for production is present.

        Returns:
            True if valid, False otherwise
        """
        errors = []

        if not self.anthropic_api_key:
            errors.append("ANTHROPIC_API_KEY is required for production")

        if errors:
            for error in errors:
                print(f"Configuration Error: {error}")
            return False

        return True


# Global settings instance
settings = Settings()

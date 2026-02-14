"""
Configuration settings for ElvAgent using Pydantic Settings.
Loads configuration from environment variables with type validation.
"""
from pathlib import Path
from typing import Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Project paths
    project_root: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent)

    # Claude API
    anthropic_api_key: str = Field(..., description="Anthropic API key for Claude")
    anthropic_model: str = Field(
        default="claude-sonnet-4-5-20250929",
        description="Default Claude model to use"
    )

    # Social Media - Discord
    discord_webhook_url: Optional[str] = Field(None, description="Discord webhook URL")

    # Social Media - Twitter
    twitter_api_key: Optional[str] = None
    twitter_api_secret: Optional[str] = None
    twitter_access_token: Optional[str] = None
    twitter_access_secret: Optional[str] = None

    # Social Media - Instagram
    instagram_access_token: Optional[str] = None
    instagram_business_account_id: Optional[str] = None

    # Social Media - Telegram
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # Image Generation
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key for DALL-E")

    # Content Sources
    crunchbase_api_key: Optional[str] = Field(None, description="Crunchbase API key (optional)")

    # Database
    database_path: Path = Field(
        default_factory=lambda: Path("/home/elvern/ElvAgent/data/state.db"),
        description="Path to SQLite database"
    )

    # Cost limits
    max_daily_cost: float = Field(default=5.0, description="Maximum daily API cost in USD")

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


# Global settings instance
settings = Settings()

"""
Discord publisher for posting newsletters via webhooks.
"""

from typing import Any

import httpx

from src.config.settings import settings
from src.models.newsletter import Newsletter
from src.publishing.base import BasePublisher, PublishResult
from src.publishing.formatters.discord_formatter import DiscordFormatter


class DiscordPublisher(BasePublisher):
    """Publish newsletters to Discord via webhooks."""

    def __init__(self):
        """Initialize Discord publisher."""
        super().__init__("discord")
        self.formatter = DiscordFormatter()
        self.webhook_url = settings.discord_webhook_url

    def validate_credentials(self) -> bool:
        """
        Check if webhook URL is configured.

        Returns:
            True if webhook URL is valid, False otherwise
        """
        return bool(self.webhook_url and self.webhook_url.startswith("https://"))

    async def format_content(self, newsletter: Newsletter) -> dict[str, Any]:
        """
        Format newsletter for Discord.

        Args:
            newsletter: Newsletter object to format

        Returns:
            Discord webhook payload dictionary
        """
        return self.formatter.format(newsletter)

    async def publish(self, content: dict[str, Any]) -> PublishResult:
        """
        Post to Discord webhook.

        Args:
            content: Discord webhook payload

        Returns:
            PublishResult with success/failure info
        """
        if not self.validate_credentials():
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error="Discord webhook URL not configured or invalid",
            )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.webhook_url, json=content, headers={"Content-Type": "application/json"}
                )

                response.raise_for_status()

                self.logger.info("discord_published", status_code=response.status_code)

                return PublishResult(
                    platform=self.platform_name,
                    success=True,
                    message="Published to Discord",
                    metadata={"status_code": response.status_code},
                )

        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP {e.response.status_code}: {e.response.text}"
            self.logger.error("discord_http_error", error=error_msg)
            return PublishResult(platform=self.platform_name, success=False, error=error_msg)

        except httpx.TimeoutException as e:
            error_msg = f"Request timeout: {str(e)}"
            self.logger.error("discord_timeout_error", error=error_msg)
            return PublishResult(platform=self.platform_name, success=False, error=error_msg)

        except Exception as e:
            self.logger.error("discord_publish_failed", error=str(e))
            return PublishResult(platform=self.platform_name, success=False, error=str(e))

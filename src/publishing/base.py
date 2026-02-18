"""
Base publisher class that all platform publishers inherit from.
Defines the interface for content publishing operations.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.models.newsletter import Newsletter
from src.utils.logger import get_logger
from src.utils.rate_limiter import rate_limiter


class PublishResult:
    """Result of a publishing operation."""

    def __init__(
        self,
        platform: str,
        success: bool,
        message: str | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        """
        Initialize publish result.

        Args:
            platform: Platform name
            success: Whether publishing succeeded
            message: Success message or published content link
            error: Error message if failed
            metadata: Additional metadata (post IDs, URLs, etc.)
        """
        self.platform = platform
        self.success = success
        self.message = message
        self.error = error
        self.metadata = metadata or {}

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "platform": self.platform,
            "success": self.success,
            "message": self.message,
            "error": self.error,
            "metadata": self.metadata,
        }


class BasePublisher(ABC):
    """
    Abstract base class for all platform publishers.

    Each publisher implementation must:
    1. Format content for the platform
    2. Handle platform-specific authentication
    3. Publish content with rate limiting
    4. Handle errors and retries
    """

    def __init__(self, platform_name: str):
        """
        Initialize base publisher.

        Args:
            platform_name: Name of the platform (e.g., 'discord', 'twitter')
        """
        self.platform_name = platform_name
        self.logger = get_logger(f"publisher.{platform_name}")

    @abstractmethod
    async def format_content(self, newsletter: Newsletter) -> Any:
        """
        Format newsletter content for this platform.

        Args:
            newsletter: Newsletter object to format

        Returns:
            Platform-specific formatted content
        """
        pass

    @abstractmethod
    async def publish(self, content: Any) -> PublishResult:
        """
        Publish content to platform.

        Args:
            content: Formatted content ready for publishing

        Returns:
            PublishResult with success/failure info
        """
        pass

    async def publish_newsletter(self, newsletter: Newsletter | dict[str, Any]) -> PublishResult:
        """
        Main publishing method.
        Formats content and publishes with rate limiting.

        Args:
            newsletter: Newsletter object or dictionary (for backward compatibility)

        Returns:
            PublishResult
        """
        # Convert dict to Newsletter object if needed
        if isinstance(newsletter, dict):
            newsletter = Newsletter.from_dict(newsletter)
        self.logger.info("starting_publish", platform=self.platform_name)

        try:
            # Format content for platform
            formatted_content = await self.format_content(newsletter)

            # Acquire rate limit token
            await rate_limiter.acquire(self.platform_name)

            # Publish content
            result = await self.publish(formatted_content)

            if result.success:
                self.logger.info(
                    "publish_success", platform=self.platform_name, message=result.message
                )
            else:
                self.logger.error("publish_failed", platform=self.platform_name, error=result.error)

            return result

        except Exception as e:
            self.logger.error(
                "publish_error",
                platform=self.platform_name,
                error=str(e),
                error_type=type(e).__name__,
            )

            return PublishResult(platform=self.platform_name, success=False, error=str(e))

    def validate_credentials(self) -> bool:
        """
        Validate that required credentials are configured.

        Returns:
            True if credentials are valid, False otherwise
        """
        # Override in subclass if needed
        return True

    def truncate_text(self, text: str, max_length: int, suffix: str = "...") -> str:
        """
        Truncate text to maximum length.

        Args:
            text: Text to truncate
            max_length: Maximum length
            suffix: Suffix to add if truncated

        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text

        truncate_at = max_length - len(suffix)
        return text[:truncate_at].rstrip() + suffix

    def split_into_chunks(self, text: str, chunk_size: int, separator: str = "\n\n") -> list[str]:
        """
        Split text into chunks for platforms with character limits.

        Args:
            text: Text to split
            chunk_size: Maximum chunk size
            separator: Preferred split separator

        Returns:
            List of text chunks
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        remaining = text

        while remaining:
            if len(remaining) <= chunk_size:
                chunks.append(remaining)
                break

            # Try to split at separator
            split_at = remaining.rfind(separator, 0, chunk_size)

            if split_at == -1:
                # No separator found, split at word boundary
                split_at = remaining.rfind(" ", 0, chunk_size)

            if split_at == -1:
                # No word boundary, hard split
                split_at = chunk_size

            chunks.append(remaining[:split_at].rstrip())
            remaining = remaining[split_at:].lstrip()

        return chunks

"""
Markdown publisher for writing newsletters to markdown files.
"""

from src.config.settings import settings
from src.models.newsletter import Newsletter
from src.publishing.base import BasePublisher, PublishResult
from src.publishing.formatters.markdown_formatter import MarkdownFormatter


class MarkdownPublisher(BasePublisher):
    """Publish newsletters as markdown files to the filesystem."""

    def __init__(self):
        """Initialize markdown publisher."""
        super().__init__("markdown")
        self.formatter = MarkdownFormatter()

        # Ensure output directory exists
        self.output_dir = settings.newsletters_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def format_content(self, newsletter: Newsletter) -> str:
        """
        Format newsletter as markdown.

        Args:
            newsletter: Newsletter object to format

        Returns:
            Markdown-formatted string
        """
        return self.formatter.format(newsletter)

    async def publish(self, content: str, newsletter: Newsletter) -> PublishResult:
        """
        Write markdown file to disk.

        Args:
            content: Formatted markdown content
            newsletter: Newsletter object (for metadata)

        Returns:
            PublishResult with success/failure info
        """
        try:
            # Generate filename: newsletters/2026-02-15-10.md
            filename = f"{newsletter.date}.md"
            filepath = self.output_dir / filename

            # Write file
            filepath.write_text(content, encoding="utf-8")

            self.logger.info("markdown_published", filepath=str(filepath), size_bytes=len(content))

            return PublishResult(
                platform=self.platform_name,
                success=True,
                message=f"Published to {filepath}",
                metadata={"filepath": str(filepath), "size": len(content), "filename": filename},
            )

        except Exception as e:
            self.logger.error("markdown_publish_failed", error=str(e))
            return PublishResult(platform=self.platform_name, success=False, error=str(e))

    async def publish_newsletter(self, newsletter: Newsletter) -> PublishResult:
        """
        Main publishing method for markdown.

        Args:
            newsletter: Newsletter object to publish

        Returns:
            PublishResult
        """
        self.logger.info("starting_publish", platform=self.platform_name)

        try:
            # Format content
            formatted_content = await self.format_content(newsletter)

            # Publish (no rate limiting needed for file writes)
            result = await self.publish(formatted_content, newsletter)

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

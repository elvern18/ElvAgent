"""
Telegram publisher for posting newsletters to Telegram channels/groups.
Uses Telegram Bot API.
"""
from typing import List
from telegram import Bot
from telegram.constants import ParseMode
from telegram.error import TelegramError
from src.publishing.base import BasePublisher, PublishResult
from src.publishing.formatters.telegram_formatter import TelegramFormatter
from src.models.newsletter import Newsletter
from src.models.enhanced_newsletter import CategoryMessage
from src.config.settings import settings


class TelegramPublisher(BasePublisher):
    """Publish newsletters to Telegram channels/groups."""

    def __init__(self):
        """Initialize Telegram publisher."""
        super().__init__("telegram")
        self.formatter = TelegramFormatter()
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.bot = None

        # Initialize bot if credentials available
        if self.validate_credentials():
            try:
                self.bot = Bot(token=self.bot_token)
                self.logger.info("telegram_bot_initialized")
            except Exception as e:
                self.logger.error(
                    "telegram_bot_init_failed",
                    error=str(e)
                )

    def validate_credentials(self) -> bool:
        """
        Check if Telegram credentials are configured.

        Returns:
            True if credentials are present, False otherwise
        """
        return bool(self.bot_token and self.chat_id)

    async def format_content(self, newsletter: Newsletter) -> List[str]:
        """
        Format newsletter as Telegram messages.

        Args:
            newsletter: Newsletter object to format

        Returns:
            List of message strings
        """
        return self.formatter.format(newsletter)

    async def publish(self, content: List[str]) -> PublishResult:
        """
        Post messages to Telegram.

        Args:
            content: List of message strings

        Returns:
            PublishResult with success/failure info
        """
        if not self.validate_credentials():
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error="Telegram credentials not configured"
            )

        if not self.bot:
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error="Telegram bot not initialized"
            )

        try:
            message_ids = []

            # Send each message
            for i, message_text in enumerate(content):
                self.logger.info(
                    "sending_message",
                    message_number=i + 1,
                    total_messages=len(content),
                    length=len(message_text)
                )

                # Send message with MarkdownV2 formatting
                message = await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=message_text,
                    parse_mode=ParseMode.MARKDOWN_V2,
                    disable_web_page_preview=False
                )

                message_ids.append(message.message_id)

                self.logger.info(
                    "message_sent",
                    message_number=i + 1,
                    message_id=message.message_id
                )

            self.logger.info(
                "messages_posted",
                message_count=len(message_ids)
            )

            return PublishResult(
                platform=self.platform_name,
                success=True,
                message=f"Posted {len(message_ids)} message(s) to Telegram",
                metadata={
                    "message_count": len(message_ids),
                    "message_ids": message_ids,
                    "chat_id": self.chat_id
                }
            )

        except TelegramError as e:
            error_msg = f"Telegram API error: {str(e)}"
            self.logger.error("telegram_api_error", error=error_msg)
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error=error_msg
            )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error("telegram_publish_failed", error=error_msg)
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error=error_msg
            )

    async def publish_enhanced(
        self,
        category_messages: List[CategoryMessage]
    ) -> PublishResult:
        """
        Publish enhanced category messages to Telegram.

        Args:
            category_messages: List of CategoryMessage objects

        Returns:
            PublishResult with success/failure info
        """
        # Format category messages
        formatted_messages = self.formatter.format_enhanced(category_messages)

        # Use existing publish method
        return await self.publish(formatted_messages)

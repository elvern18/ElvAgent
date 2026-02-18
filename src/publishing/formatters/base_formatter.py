"""
Base formatter class for all platform formatters.
"""

from abc import ABC, abstractmethod

from src.models.newsletter import Newsletter, NewsletterItem


class BaseFormatter(ABC):
    """
    Base class for all platform formatters.

    Each formatter is responsible for converting a Newsletter object
    into a platform-specific format (string, dict, etc.).
    """

    def __init__(self, platform_name: str):
        """
        Initialize base formatter.

        Args:
            platform_name: Name of the platform (e.g., 'markdown', 'discord')
        """
        self.platform_name = platform_name

    @abstractmethod
    def format(self, newsletter: Newsletter):
        """
        Format newsletter for this platform.

        Args:
            newsletter: Newsletter object to format

        Returns:
            Platform-specific formatted content (type varies by platform)
        """
        pass

    def format_item(self, item: NewsletterItem, index: int) -> str:
        """
        Format single newsletter item (can override in subclass).

        Args:
            item: Newsletter item
            index: Item number (1-based)

        Returns:
            Formatted item string
        """
        return f"{index}. {item.title}\n{item.summary}\n{item.url}"

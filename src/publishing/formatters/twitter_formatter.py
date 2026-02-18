"""
Twitter formatter for converting newsletters to tweet threads.
Handles 280-character limit and thread structure.
"""

from src.models.newsletter import Newsletter
from src.publishing.formatters.base_formatter import BaseFormatter


class TwitterFormatter(BaseFormatter):
    """Format newsletters as Twitter threads."""

    MAX_TWEET_LENGTH = 280
    THREAD_INTRO_TEMPLATE = "🤖 AI News Update - {date}\n\n{summary}"
    ITEM_TEMPLATE = "{index}. {title}\n\n{summary}\n\n🔗 {url}"

    def __init__(self):
        """Initialize Twitter formatter."""
        super().__init__(platform_name="twitter")

    def format(self, newsletter: Newsletter) -> list[str]:
        """
        Format newsletter as a list of tweets (thread).

        Args:
            newsletter: Newsletter object to format

        Returns:
            List of tweet strings (each <= 280 chars)
        """
        tweets = []

        # Tweet 1: Introduction with summary
        intro = self._format_intro(newsletter)
        tweets.append(intro)

        # Tweets 2+: Individual items
        for i, item in enumerate(newsletter.items, 1):
            item_tweet = self._format_item(item, i)

            # If item is too long, split it
            if len(item_tweet) > self.MAX_TWEET_LENGTH:
                item_tweets = self._split_item(item, i)
                tweets.extend(item_tweets)
            else:
                tweets.append(item_tweet)

        return tweets

    def _format_intro(self, newsletter: Newsletter) -> str:
        """
        Format introduction tweet.

        Args:
            newsletter: Newsletter object

        Returns:
            Introduction tweet (truncated if needed)
        """
        # Format date nicely (2026-02-16-10 -> Feb 16, 10:00)
        date_parts = newsletter.date.split("-")
        if len(date_parts) == 4:
            month_names = [
                "Jan",
                "Feb",
                "Mar",
                "Apr",
                "May",
                "Jun",
                "Jul",
                "Aug",
                "Sep",
                "Oct",
                "Nov",
                "Dec",
            ]
            month = month_names[int(date_parts[1]) - 1]
            day = date_parts[2]
            hour = date_parts[3]
            formatted_date = f"{month} {day}, {hour}:00"
        else:
            formatted_date = newsletter.date

        intro = self.THREAD_INTRO_TEMPLATE.format(date=formatted_date, summary=newsletter.summary)

        # Truncate if too long
        if len(intro) > self.MAX_TWEET_LENGTH:
            max_summary_len = (
                self.MAX_TWEET_LENGTH
                - len(self.THREAD_INTRO_TEMPLATE.format(date=formatted_date, summary=""))
                - 3
            )  # for "..."

            truncated_summary = newsletter.summary[:max_summary_len] + "..."
            intro = self.THREAD_INTRO_TEMPLATE.format(
                date=formatted_date, summary=truncated_summary
            )

        return intro

    def _format_item(self, item, index: int) -> str:
        """
        Format a single newsletter item.

        Args:
            item: NewsletterItem object
            index: Item number in the list

        Returns:
            Formatted tweet string
        """
        return self.ITEM_TEMPLATE.format(
            index=index, title=item.title, summary=item.summary, url=item.url
        )

    def _split_item(self, item, index: int) -> list[str]:
        """
        Split a long item into multiple tweets.

        Args:
            item: NewsletterItem object
            index: Item number

        Returns:
            List of tweet strings
        """
        tweets = []

        # First tweet: Title + URL
        first_tweet = f"{index}. {item.title}\n\n🔗 {item.url}"

        # If title itself is too long, truncate it
        if len(first_tweet) > self.MAX_TWEET_LENGTH:
            max_title_len = self.MAX_TWEET_LENGTH - len(f"{index}. \n\n🔗 {item.url}") - 3
            truncated_title = item.title[:max_title_len] + "..."
            first_tweet = f"{index}. {truncated_title}\n\n🔗 {item.url}"

        tweets.append(first_tweet)

        # Second tweet: Summary (truncated if needed)
        summary_tweet = item.summary
        if len(summary_tweet) > self.MAX_TWEET_LENGTH:
            summary_tweet = summary_tweet[: self.MAX_TWEET_LENGTH - 3] + "..."

        tweets.append(summary_tweet)

        return tweets

    def _truncate_text(self, text: str, max_length: int) -> str:
        """
        Truncate text to fit within max length.

        Args:
            text: Text to truncate
            max_length: Maximum length

        Returns:
            Truncated text with ellipsis
        """
        if len(text) <= max_length:
            return text

        return text[: max_length - 3] + "..."

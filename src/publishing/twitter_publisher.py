"""
Twitter/X publisher for posting newsletters as threads.
Uses OAuth 1.0a authentication via tweepy.
"""

import tweepy

from src.config.settings import settings
from src.models.newsletter import Newsletter
from src.publishing.base import BasePublisher, PublishResult
from src.publishing.formatters.twitter_formatter import TwitterFormatter


class TwitterPublisher(BasePublisher):
    """Publish newsletters to Twitter/X as threads."""

    def __init__(self):
        """Initialize Twitter publisher."""
        super().__init__("twitter")
        self.formatter = TwitterFormatter()
        self.api = None
        self.client = None  # Keep for backward compatibility

        # Initialize Twitter API client if credentials are available
        if self.validate_credentials():
            try:
                # OAuth 1.0a authentication
                auth = tweepy.OAuthHandler(settings.twitter_api_key, settings.twitter_api_secret)
                auth.set_access_token(settings.twitter_access_token, settings.twitter_access_secret)

                # Use API v1.1 (works with Essential tier for posting)
                # v2 requires Elevated access for write operations
                self.api = tweepy.API(auth)
                self.client = None  # Not using v2

                self.logger.info("twitter_client_initialized", api_version="v1.1")

            except Exception as e:
                self.logger.error("twitter_client_init_failed", error=str(e))

    def validate_credentials(self) -> bool:
        """
        Check if Twitter credentials are configured.

        Returns:
            True if all credentials are present, False otherwise
        """
        return all(
            [
                settings.twitter_api_key,
                settings.twitter_api_secret,
                settings.twitter_access_token,
                settings.twitter_access_secret,
            ]
        )

    async def format_content(self, newsletter: Newsletter) -> list[str]:
        """
        Format newsletter as Twitter thread.

        Args:
            newsletter: Newsletter object to format

        Returns:
            List of tweet strings
        """
        return self.formatter.format(newsletter)

    async def publish(self, content: list[str]) -> PublishResult:
        """
        Post Twitter thread.

        Args:
            content: List of tweets to post as a thread

        Returns:
            PublishResult with success/failure info
        """
        if not self.validate_credentials():
            return PublishResult(
                platform=self.platform_name,
                success=False,
                error="Twitter credentials not configured",
            )

        if not self.api:
            return PublishResult(
                platform=self.platform_name, success=False, error="Twitter API not initialized"
            )

        try:
            tweet_ids = []
            previous_tweet_id = None

            # Post each tweet in the thread using API v1.1
            for i, tweet_text in enumerate(content):
                self.logger.info(
                    "posting_tweet",
                    tweet_number=i + 1,
                    total_tweets=len(content),
                    length=len(tweet_text),
                )

                # Post tweet (reply to previous if in thread)
                if previous_tweet_id:
                    # Reply to previous tweet
                    status = self.api.update_status(
                        status=tweet_text,
                        in_reply_to_status_id=previous_tweet_id,
                        auto_populate_reply_metadata=True,
                    )
                else:
                    # First tweet in thread
                    status = self.api.update_status(status=tweet_text)

                tweet_id = status.id_str
                tweet_ids.append(tweet_id)
                previous_tweet_id = tweet_id

                self.logger.info("tweet_posted", tweet_number=i + 1, tweet_id=tweet_id)

            # Build thread URL (first tweet)
            # Get authenticated user's screen name for proper URL
            user = self.api.verify_credentials()
            screen_name = user.screen_name
            thread_url = (
                f"https://twitter.com/{screen_name}/status/{tweet_ids[0]}" if tweet_ids else None
            )

            self.logger.info("thread_posted", tweet_count=len(tweet_ids), thread_url=thread_url)

            return PublishResult(
                platform=self.platform_name,
                success=True,
                message=f"Posted {len(tweet_ids)}-tweet thread",
                metadata={
                    "tweet_count": len(tweet_ids),
                    "tweet_ids": tweet_ids,
                    "thread_url": thread_url,
                },
            )

        except tweepy.TweepyException as e:
            error_msg = f"Twitter API error: {str(e)}"
            self.logger.error("twitter_api_error", error=error_msg)
            return PublishResult(platform=self.platform_name, success=False, error=error_msg)

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            self.logger.error("twitter_publish_failed", error=error_msg)
            return PublishResult(platform=self.platform_name, success=False, error=error_msg)

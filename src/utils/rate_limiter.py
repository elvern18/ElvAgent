"""
Rate limiting utilities to prevent API quota exhaustion.
Uses token bucket algorithm for smooth rate limiting.
"""
import time
import asyncio
from collections import defaultdict
from typing import Dict
from src.config.constants import RATE_LIMITS
from src.utils.logger import get_logger

logger = get_logger("rate_limiter")


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self):
        """Initialize rate limiter."""
        self.buckets: Dict[str, float] = defaultdict(float)
        self.last_update: Dict[str, float] = defaultdict(float)

    def _refill_bucket(self, service: str, limit: int) -> float:
        """
        Refill the token bucket based on elapsed time.

        Args:
            service: Service name (e.g., 'twitter', 'anthropic')
            limit: Rate limit (requests per minute)

        Returns:
            Current token count in bucket
        """
        now = time.time()

        if service not in self.last_update:
            self.last_update[service] = now
            self.buckets[service] = float(limit)
            return self.buckets[service]

        # Calculate tokens to add based on elapsed time
        elapsed = now - self.last_update[service]
        tokens_to_add = (elapsed / 60.0) * limit  # Refill rate per second

        # Update bucket (capped at limit)
        self.buckets[service] = min(
            float(limit),
            self.buckets[service] + tokens_to_add
        )
        self.last_update[service] = now

        return self.buckets[service]

    async def acquire(self, service: str, tokens: int = 1) -> None:
        """
        Acquire tokens from the rate limiter (async).
        Waits if insufficient tokens are available.

        Args:
            service: Service name
            tokens: Number of tokens to acquire (default 1)
        """
        limit = RATE_LIMITS.get(service, 50)  # Default to 50 req/min

        while True:
            current = self._refill_bucket(service, limit)

            if current >= tokens:
                self.buckets[service] -= tokens
                logger.debug(
                    "rate_limit_acquired",
                    service=service,
                    tokens_used=tokens,
                    tokens_remaining=self.buckets[service]
                )
                return

            # Calculate wait time
            tokens_needed = tokens - current
            wait_time = (tokens_needed / limit) * 60.0

            logger.info(
                "rate_limit_waiting",
                service=service,
                wait_seconds=f"{wait_time:.2f}",
                tokens_needed=tokens_needed
            )

            await asyncio.sleep(wait_time)

    def acquire_sync(self, service: str, tokens: int = 1) -> None:
        """
        Acquire tokens from the rate limiter (synchronous).
        Waits if insufficient tokens are available.

        Args:
            service: Service name
            tokens: Number of tokens to acquire (default 1)
        """
        limit = RATE_LIMITS.get(service, 50)

        while True:
            current = self._refill_bucket(service, limit)

            if current >= tokens:
                self.buckets[service] -= tokens
                logger.debug(
                    "rate_limit_acquired",
                    service=service,
                    tokens_used=tokens,
                    tokens_remaining=self.buckets[service]
                )
                return

            # Calculate wait time
            tokens_needed = tokens - current
            wait_time = (tokens_needed / limit) * 60.0

            logger.info(
                "rate_limit_waiting",
                service=service,
                wait_seconds=f"{wait_time:.2f}",
                tokens_needed=tokens_needed
            )

            time.sleep(wait_time)


# Global rate limiter instance
rate_limiter = RateLimiter()

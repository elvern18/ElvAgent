"""
Retry utilities with exponential backoff for handling transient failures.
"""

import asyncio
from collections.abc import Callable
from typing import Any, TypeVar

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config.constants import MAX_RETRIES, RETRY_MAX_WAIT, RETRY_MIN_WAIT
from src.utils.logger import get_logger

logger = get_logger("retry")

T = TypeVar("T")


def create_retry_decorator(
    max_attempts: int = MAX_RETRIES,
    min_wait: int = RETRY_MIN_WAIT,
    max_wait: int = RETRY_MAX_WAIT,
    retry_exceptions: tuple = (Exception,),
):
    """
    Create a retry decorator with exponential backoff.

    Args:
        max_attempts: Maximum number of retry attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        retry_exceptions: Tuple of exception types to retry on

    Returns:
        Retry decorator
    """
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
        retry=retry_if_exception_type(retry_exceptions),
        reraise=True,
    )


async def retry_async(
    func: Callable[..., Any],
    *args,
    max_attempts: int = MAX_RETRIES,
    min_wait: float = RETRY_MIN_WAIT,
    max_wait: float = RETRY_MAX_WAIT,
    **kwargs,
) -> Any:
    """
    Retry an async function with exponential backoff.

    Args:
        func: Async function to retry
        *args: Positional arguments for func
        max_attempts: Maximum number of attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        **kwargs: Keyword arguments for func

    Returns:
        Result from successful function call

    Raises:
        Last exception if all retries fail
    """
    last_exception = None
    wait_time = min_wait

    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(
                "retry_attempt", function=func.__name__, attempt=attempt, max_attempts=max_attempts
            )
            return await func(*args, **kwargs)

        except Exception as e:
            last_exception = e
            logger.warning(
                "retry_failed_attempt",
                function=func.__name__,
                attempt=attempt,
                max_attempts=max_attempts,
                error=str(e),
                error_type=type(e).__name__,
            )

            if attempt < max_attempts:
                logger.info("retry_waiting", function=func.__name__, wait_seconds=wait_time)
                await asyncio.sleep(wait_time)
                # Exponential backoff
                wait_time = min(wait_time * 2, max_wait)
            else:
                logger.error(
                    "retry_exhausted",
                    function=func.__name__,
                    total_attempts=max_attempts,
                    final_error=str(e),
                )

    # All retries exhausted
    if last_exception:
        raise last_exception


def retry_sync(
    func: Callable[..., Any],
    *args,
    max_attempts: int = MAX_RETRIES,
    min_wait: float = RETRY_MIN_WAIT,
    max_wait: float = RETRY_MAX_WAIT,
    **kwargs,
) -> Any:
    """
    Retry a synchronous function with exponential backoff.

    Args:
        func: Function to retry
        *args: Positional arguments for func
        max_attempts: Maximum number of attempts
        min_wait: Minimum wait time in seconds
        max_wait: Maximum wait time in seconds
        **kwargs: Keyword arguments for func

    Returns:
        Result from successful function call

    Raises:
        Last exception if all retries fail
    """
    import time

    last_exception = None
    wait_time = min_wait

    for attempt in range(1, max_attempts + 1):
        try:
            logger.debug(
                "retry_attempt", function=func.__name__, attempt=attempt, max_attempts=max_attempts
            )
            return func(*args, **kwargs)

        except Exception as e:
            last_exception = e
            logger.warning(
                "retry_failed_attempt",
                function=func.__name__,
                attempt=attempt,
                max_attempts=max_attempts,
                error=str(e),
                error_type=type(e).__name__,
            )

            if attempt < max_attempts:
                logger.info("retry_waiting", function=func.__name__, wait_seconds=wait_time)
                time.sleep(wait_time)
                # Exponential backoff
                wait_time = min(wait_time * 2, max_wait)
            else:
                logger.error(
                    "retry_exhausted",
                    function=func.__name__,
                    total_attempts=max_attempts,
                    final_error=str(e),
                )

    # All retries exhausted
    if last_exception:
        raise last_exception

"""Unit tests for utility modules: CostTracker, RateLimiter, retry, logger."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.cost_tracker import CostTracker
from src.utils.logger import configure_logging, get_logger
from src.utils.rate_limiter import RateLimiter
from src.utils.retry import create_retry_decorator, retry_async, retry_sync

# ── CostTracker ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestCostTracker:
    def setup_method(self):
        self.tracker = CostTracker()

    def test_estimate_cost_token_model(self):
        cost = self.tracker.estimate_cost(
            "anthropic",
            "claude-haiku-3-5-20241022",
            input_tokens=1000,
            output_tokens=1000,
        )
        expected = (1000 / 1000) * 0.00025 + (1000 / 1000) * 0.00125
        assert cost == pytest.approx(expected)

    def test_estimate_cost_image_model(self):
        cost = self.tracker.estimate_cost(
            "openai",
            "dall-e-3",
            image_count=3,
        )
        assert cost == pytest.approx(3 * 0.02)

    def test_estimate_cost_unknown_model(self):
        cost = self.tracker.estimate_cost("unknown", "no-such-model")
        assert cost == 0.0

    def test_track_usage_accumulates(self):
        model = "claude-haiku-3-5-20241022"
        r1 = self.tracker.track_usage("anthropic", model, input_tokens=500, output_tokens=500)
        r2 = self.tracker.track_usage("anthropic", model, input_tokens=500, output_tokens=500)
        assert r2["daily_requests"] == 2
        assert r2["daily_cost"] == pytest.approx(r1["cost"] * 2)

    def test_get_daily_total(self):
        model = "claude-haiku-3-5-20241022"
        self.tracker.track_usage("anthropic", model, input_tokens=1000, output_tokens=0)
        self.tracker.track_usage("openai", "dall-e-3", image_count=1)
        total = self.tracker.get_daily_total()
        expected = (1000 / 1000) * 0.00025 + 0.02
        assert total == pytest.approx(expected)

    def test_get_daily_total_different_date(self):
        total = self.tracker.get_daily_total("1999-01-01")
        assert total == 0.0

    def test_check_budget_within(self):
        assert self.tracker.check_budget(5.0) is True

    def test_check_budget_exceeded(self):
        self.tracker.track_usage("openai", "dall-e-3", image_count=100)
        assert self.tracker.check_budget(1.0) is False

    def test_get_metrics(self):
        model = "claude-haiku-3-5-20241022"
        self.tracker.track_usage("anthropic", model, input_tokens=1000, output_tokens=500)
        metrics = self.tracker.get_metrics()
        assert "anthropic" in metrics
        assert metrics["anthropic"]["requests"] == 1
        assert metrics["anthropic"]["tokens"] == 1500


# ── RateLimiter ──────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRateLimiter:
    def setup_method(self):
        self.limiter = RateLimiter()

    @pytest.mark.asyncio
    async def test_acquire_no_wait_when_tokens_available(self):
        self.limiter.buckets["test"] = 50.0
        self.limiter.last_update["test"] = time.time()
        await self.limiter.acquire("test", tokens=1)
        # Default rate limit is 50, bucket capped at 50; after acquiring 1 token ~49
        assert self.limiter.buckets["test"] >= 48.0

    @pytest.mark.asyncio
    async def test_acquire_waits_when_exhausted(self):
        self.limiter.buckets["test"] = 0.0
        self.limiter.last_update["test"] = time.time()
        with patch("src.utils.rate_limiter.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # After sleep, refill will add tokens via elapsed time
            # We simulate by adding tokens on first sleep call
            async def add_tokens(duration):
                self.limiter.buckets["test"] = 50.0

            mock_sleep.side_effect = add_tokens
            await self.limiter.acquire("test", tokens=1)
            mock_sleep.assert_called_once()

    def test_acquire_sync_waits_when_exhausted(self):
        self.limiter.buckets["test"] = 0.0
        self.limiter.last_update["test"] = time.time()
        with patch("src.utils.rate_limiter.time.sleep") as mock_sleep:

            def add_tokens(duration):
                self.limiter.buckets["test"] = 50.0

            mock_sleep.side_effect = add_tokens
            self.limiter.acquire_sync("test", tokens=1)
            mock_sleep.assert_called_once()


# ── Retry ────────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestRetry:
    @pytest.mark.asyncio
    async def test_retry_async_succeeds_first_try(self):
        func = AsyncMock(return_value="ok")
        result = await retry_async(func, max_attempts=3, min_wait=0.01)
        assert result == "ok"
        assert func.call_count == 1

    @pytest.mark.asyncio
    async def test_retry_async_succeeds_after_failures(self):
        func = AsyncMock(side_effect=[ValueError("fail"), ValueError("fail"), "ok"])
        with patch("src.utils.retry.asyncio.sleep", new_callable=AsyncMock):
            result = await retry_async(func, max_attempts=3, min_wait=0.01)
        assert result == "ok"
        assert func.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_async_exhausted(self):
        func = AsyncMock(side_effect=ValueError("always fails"))
        with patch("src.utils.retry.asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(ValueError, match="always fails"):
                await retry_async(func, max_attempts=2, min_wait=0.01)
        assert func.call_count == 2

    def test_retry_sync_succeeds_after_failure(self):
        func = MagicMock(side_effect=[RuntimeError("err"), "ok"])
        func.__name__ = "mock_func"
        with patch("time.sleep"):
            result = retry_sync(func, max_attempts=3, min_wait=0.01)
        assert result == "ok"
        assert func.call_count == 2

    def test_retry_sync_exhausted(self):
        func = MagicMock(side_effect=RuntimeError("bad"))
        func.__name__ = "mock_func"
        with patch("time.sleep"):
            with pytest.raises(RuntimeError, match="bad"):
                retry_sync(func, max_attempts=2, min_wait=0.01)
        assert func.call_count == 2

    def test_create_retry_decorator(self):
        call_count = 0

        @create_retry_decorator(max_attempts=2, min_wait=0, max_wait=0)
        def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("not yet")
            return "done"

        result = flaky()
        assert result == "done"
        assert call_count == 2


# ── Logger ───────────────────────────────────────────────────────────────


@pytest.mark.unit
class TestLogger:
    def test_get_logger_returns_logger(self):
        log = get_logger("test_module")
        assert hasattr(log, "info")
        assert hasattr(log, "debug")
        assert hasattr(log, "warning")

    def test_get_logger_no_name(self):
        log = get_logger()
        assert hasattr(log, "info")

    def test_configure_logging_no_error(self):
        log = configure_logging(log_level="DEBUG", pretty_console=False)
        assert hasattr(log, "info")

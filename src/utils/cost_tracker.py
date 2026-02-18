"""
Cost tracking for API usage across different services.
Tracks token usage and estimates costs for budgeting.
"""

from datetime import date

from src.config.constants import MODEL_COSTS
from src.utils.logger import get_logger

logger = get_logger("cost_tracker")


class CostTracker:
    """Track API costs across different services."""

    def __init__(self):
        """Initialize cost tracker."""
        self.daily_costs: dict[str, float] = {}
        self.daily_requests: dict[str, int] = {}
        self.daily_tokens: dict[str, int] = {}

    def estimate_cost(
        self,
        api_name: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        image_count: int = 0,
    ) -> float:
        """
        Estimate cost for an API call.

        Args:
            api_name: Name of the API (e.g., 'anthropic', 'openai')
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            image_count: Number of images generated (for DALL-E)

        Returns:
            Estimated cost in USD
        """
        if model not in MODEL_COSTS:
            logger.warning("unknown_model_cost", api_name=api_name, model=model)
            return 0.0

        cost_config = MODEL_COSTS[model]

        if "per_image" in cost_config:
            # Image generation cost
            cost = image_count * cost_config["per_image"]
        else:
            # Token-based cost
            input_cost = (input_tokens / 1000) * cost_config.get("input", 0)
            output_cost = (output_tokens / 1000) * cost_config.get("output", 0)
            cost = input_cost + output_cost

        return cost

    def track_usage(
        self,
        api_name: str,
        model: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        image_count: int = 0,
        request_count: int = 1,
    ) -> dict[str, float]:
        """
        Track API usage and calculate cost.

        Args:
            api_name: Name of the API
            model: Model identifier
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            image_count: Number of images generated
            request_count: Number of requests made

        Returns:
            Dictionary with cost and usage stats
        """
        cost = self.estimate_cost(
            api_name=api_name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            image_count=image_count,
        )

        # Track daily totals
        today = str(date.today())
        key = f"{today}:{api_name}"

        self.daily_costs[key] = self.daily_costs.get(key, 0.0) + cost
        self.daily_requests[key] = self.daily_requests.get(key, 0) + request_count
        total_tokens = input_tokens + output_tokens
        self.daily_tokens[key] = self.daily_tokens.get(key, 0) + total_tokens

        logger.info(
            "api_usage_tracked",
            api_name=api_name,
            model=model,
            cost=f"${cost:.4f}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_daily_cost=f"${self.daily_costs[key]:.4f}",
        )

        return {
            "cost": cost,
            "daily_cost": self.daily_costs[key],
            "daily_requests": self.daily_requests[key],
            "daily_tokens": self.daily_tokens[key],
        }

    def get_daily_total(self, target_date: str | None = None) -> float:
        """
        Get total cost for a specific date.

        Args:
            target_date: Date string (YYYY-MM-DD). Defaults to today.

        Returns:
            Total cost in USD
        """
        if target_date is None:
            target_date = str(date.today())

        total = 0.0
        for key, cost in self.daily_costs.items():
            if key.startswith(target_date):
                total += cost

        return total

    def get_metrics(self, target_date: str | None = None) -> dict[str, dict]:
        """
        Get detailed metrics for a specific date.

        Args:
            target_date: Date string (YYYY-MM-DD). Defaults to today.

        Returns:
            Dictionary of metrics by API
        """
        if target_date is None:
            target_date = str(date.today())

        metrics = {}
        for key in self.daily_costs.keys():
            if key.startswith(target_date):
                _, api_name = key.split(":", 1)
                metrics[api_name] = {
                    "cost": self.daily_costs[key],
                    "requests": self.daily_requests.get(key, 0),
                    "tokens": self.daily_tokens.get(key, 0),
                }

        return metrics

    def check_budget(self, max_daily_cost: float) -> bool:
        """
        Check if current daily spending is within budget.

        Args:
            max_daily_cost: Maximum allowed daily cost in USD

        Returns:
            True if within budget, False otherwise
        """
        total = self.get_daily_total()
        within_budget = total <= max_daily_cost

        if not within_budget:
            logger.warning(
                "budget_exceeded", current_cost=f"${total:.2f}", max_cost=f"${max_daily_cost:.2f}"
            )

        return within_budget


# Global cost tracker instance
cost_tracker = CostTracker()

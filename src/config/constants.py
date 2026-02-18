"""
Application constants and configuration values.
"""

# Content scoring thresholds
MIN_SIGNIFICANT_ITEMS = 3  # Minimum items to publish newsletter
MIN_RELEVANCE_SCORE = 5  # Minimum score (1-10) to include item
MAX_ITEMS_PER_NEWSLETTER = 15

# Research configuration
RESEARCH_TIME_WINDOW_HOURS = 24  # Look for content from last N hours
MAX_ITEMS_PER_SOURCE = 5  # Maximum items to return per researcher

# Publishing configuration
PLATFORM_NAMES = ["discord", "twitter", "instagram", "telegram", "markdown"]

# Rate limiting (requests per minute)
RATE_LIMITS = {
    "twitter": 50,
    "instagram": 25,
    "telegram": 30,
    "discord": 30,
    "openai": 50,
    "anthropic": 50,
}

# Cache TTL (seconds)
CACHE_TTL = 900  # 15 minutes

# Retry configuration
MAX_RETRIES = 3
RETRY_MIN_WAIT = 2  # seconds
RETRY_MAX_WAIT = 60  # seconds

# Model costs (per 1K tokens)
MODEL_COSTS = {
    "claude-sonnet-4-5-20250929": {"input": 0.003, "output": 0.015},
    "claude-haiku-3-5-20241022": {"input": 0.00025, "output": 0.00125},
    "claude-opus-4-5-20251101": {"input": 0.015, "output": 0.075},
    "gpt-4": {"input": 0.03, "output": 0.06},
    "dall-e-3": {"per_image": 0.02},  # Rough estimate for standard quality
}

# Content categories
CATEGORIES = [
    "research",  # Academic papers, technical research
    "product",  # New AI products, tools, features
    "funding",  # Startup funding, M&A
    "news",  # General AI news, industry updates
    "breakthrough",  # Major technical breakthroughs
    "regulation",  # Policy, regulation, ethics
]

# Platform-specific limits
PLATFORM_LIMITS = {
    "twitter": {"max_chars": 280, "max_thread_length": 25},
    "discord": {"max_chars": 2000, "max_embeds": 10},
    "telegram": {"max_chars": 4096},
    "instagram": {"max_caption_chars": 2200, "video_duration_sec": 5},
}

"""
Template-based fallbacks for content enhancement.
Used when AI enhancement fails or is disabled.
"""

import random

from src.models.newsletter import NewsletterItem

# Headline templates by category
HEADLINE_TEMPLATES: dict[str, list[str]] = {
    "research": [
        "🔬 new paper: {title}",
        "🔬 interesting: {title}",
        "🔬 worth reading: {title}",
        "🔬 from the labs: {title}",
        "🔬 {title}",
    ],
    "funding": [
        "💰 {title}",
        "💰 new raise: {title}",
        "💰 just announced: {title}",
        "💰 money moves: {title}",
        "💰 fresh funding: {title}",
    ],
    "news": [
        "🔥 {title}",
        "🔥 just in: {title}",
        "🔥 worth watching: {title}",
        "🔥 happening now: {title}",
        "🔥 icymi: {title}",
    ],
    "product": [
        "🚀 just shipped: {title}",
        "🚀 new drop: {title}",
        "🚀 {title}",
        "🚀 just dropped: {title}",
        "🚀 check this out: {title}",
    ],
    "regulation": [
        "📜 policy watch: {title}",
        "📜 {title}",
        "📜 heads up: {title}",
        "📜 new rules: {title}",
        "📜 worth knowing: {title}",
    ],
}

# Takeaway templates by category
TAKEAWAY_TEMPLATES: dict[str, list[str]] = {
    "research": [
        "interesting work on {topic}. worth keeping an eye on.",
        "new approach to {topic}. curious how it holds up.",
        "could change how we think about {topic}. maybe.",
        "niche but {topic} actually matters here.",
    ],
    "funding": [
        "more money into {topic}. pattern is clear.",
        "investors clearly see something in {topic}.",
        "validates the market for {topic}. probably.",
        "another bet on {topic}. getting hard to ignore.",
    ],
    "news": [
        "worth watching. {topic} is moving fast.",
        "not sure what to make of this yet. {topic} is shifting.",
        "matters for {topic}. we'll see how it plays out.",
        "{topic} keeps coming up. probably means something.",
    ],
    "product": [
        "makes {topic} more accessible. that's the point.",
        "{topic} just got easier. useful if you need it.",
        "interesting approach to {topic}.",
        "solves a real problem with {topic}.",
    ],
    "regulation": [
        "new rules for {topic}. worth knowing.",
        "could reshape how {topic} works.",
        "matters for anyone working on {topic}.",
        "{topic} is getting regulated. was a matter of time.",
    ],
}


def get_template_headline(item: NewsletterItem) -> str:
    """
    Generate template-based headline as fallback.

    Args:
        item: NewsletterItem to create headline for

    Returns:
        Template-based headline string
    """
    # Get templates for category, default to news
    templates = HEADLINE_TEMPLATES.get(item.category, HEADLINE_TEMPLATES["news"])

    # Select random template
    template = random.choice(templates)

    # Truncate title if too long
    title = item.title
    if len(title) > 80:
        title = title[:77] + "..."

    # Format template
    return template.format(title=title)


def get_template_takeaway(item: NewsletterItem) -> str:
    """
    Generate template-based takeaway as fallback.

    Args:
        item: NewsletterItem to create takeaway for

    Returns:
        Template-based takeaway string
    """
    # Get templates for category
    templates = TAKEAWAY_TEMPLATES.get(item.category, TAKEAWAY_TEMPLATES["news"])

    # Select random template
    template = random.choice(templates)

    # Extract topic from title (first 3 words or category name)
    words = item.title.split()[:3]
    topic = " ".join(words) if len(words) > 0 else item.category

    # Format template
    return template.format(topic=topic.lower())


def get_category_emoji(category: str) -> str:
    """
    Get emoji for category.

    Args:
        category: Category name

    Returns:
        Emoji string
    """
    emojis = {"research": "🔬", "funding": "💰", "news": "🔥", "product": "🚀", "regulation": "📜"}
    return emojis.get(category, "📌")


def get_category_title(category: str, date: str) -> str:
    """
    Get formatted title for category message.

    Args:
        category: Category name
        date: Newsletter date

    Returns:
        Formatted title string
    """
    titles = {
        "news": "🔥 the discourse",
        "funding": "💰 money moves",
        "product": "🚀 shipped",
        "research": "🔬 from the labs",
        "regulation": "📜 policy watch",
    }
    return titles.get(category, f"📌 {category}")

"""
Template-based fallbacks for content enhancement.
Used when AI enhancement fails or is disabled.
"""

import random

from src.models.newsletter import NewsletterItem

# Headline templates by category
HEADLINE_TEMPLATES: dict[str, list[str]] = {
    "research": [
        "🔬 New Research: {title}",
        "📚 Study Reveals: {title}",
        "🧪 Breakthrough: {title}",
        "📊 Research: {title}",
        "🎓 Scientists: {title}",
    ],
    "funding": [
        "💰 Investment: {title}",
        "💸 Funding: {title}",
        "🤑 Deal: {title}",
        "💵 Raised: {title}",
        "📈 Investment: {title}",
    ],
    "news": [
        "🚨 Breaking: {title}",
        "📰 News: {title}",
        "⚡ Update: {title}",
        "🔥 Hot: {title}",
        "📢 Announcement: {title}",
    ],
    "product": [
        "🚀 New Launch: {title}",
        "✨ Release: {title}",
        "🎯 New Tool: {title}",
        "💡 Innovation: {title}",
        "🛠️ Product: {title}",
    ],
    "regulation": [
        "📜 Policy Update: {title}",
        "⚖️ Regulation: {title}",
        "🏛️ Legal: {title}",
        "📋 Compliance: {title}",
        "🔒 Governance: {title}",
    ],
}

# Takeaway templates by category
TAKEAWAY_TEMPLATES: dict[str, list[str]] = {
    "research": [
        "💡 Why it matters: New insights into {topic}",
        "💡 Why it matters: Advances our understanding of {topic}",
        "💡 Why it matters: Could lead to breakthroughs in {topic}",
        "💡 Why it matters: Important development in {topic}",
    ],
    "funding": [
        "💡 Why it matters: Signals investor confidence in {topic}",
        "💡 Why it matters: Accelerates development of {topic}",
        "💡 Why it matters: Validates market demand for {topic}",
        "💡 Why it matters: Could disrupt {topic}",
    ],
    "news": [
        "💡 Why it matters: Major shift in {topic}",
        "💡 Why it matters: Impacts how we think about {topic}",
        "💡 Why it matters: Sets precedent for {topic}",
        "💡 Why it matters: Changes the landscape of {topic}",
    ],
    "product": [
        "💡 Why it matters: Makes {topic} more accessible",
        "💡 Why it matters: Solves key challenges in {topic}",
        "💡 Why it matters: New capabilities for {topic}",
        "💡 Why it matters: Democratizes access to {topic}",
    ],
    "regulation": [
        "💡 Why it matters: Shapes future of {topic}",
        "💡 Why it matters: New rules for {topic}",
        "💡 Why it matters: Impacts industry practices in {topic}",
        "💡 Why it matters: Sets standards for {topic}",
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
    emojis = {"research": "🔬", "funding": "💰", "news": "🚨", "product": "🚀", "regulation": "📜"}
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
        "news": f"🚨 AI NEWS FLASH - {date}",
        "funding": "💰 FUNDING ROUNDUP",
        "product": "🚀 NEW LAUNCHES",
        "research": "🔬 RESEARCH HIGHLIGHTS",
        "regulation": "📜 POLICY & REGULATION",
    }
    return titles.get(category, f"📌 {category.upper()}")

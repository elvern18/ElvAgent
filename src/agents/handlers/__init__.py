"""Task handlers for TaskWorker dispatch."""

from src.agents.handlers.newsletter_handler import HandlerResult, NewsletterHandler
from src.agents.handlers.status_handler import StatusHandler

__all__ = ["HandlerResult", "NewsletterHandler", "StatusHandler"]

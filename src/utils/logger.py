"""
Structured logging configuration using structlog.
Provides JSON logging for production and pretty console output for development.
"""
import sys
import logging
from pathlib import Path
from typing import Optional
import structlog
from structlog.types import Processor


def configure_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
    pretty_console: bool = True
) -> structlog.BoundLogger:
    """
    Configure structured logging with structlog.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for logging output
        pretty_console: If True, use pretty console output. If False, use JSON.

    Returns:
        Configured logger instance
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout if log_file is None else None,
        level=getattr(logging, log_level.upper()),
    )

    # Add file handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        logging.root.addHandler(file_handler)

    # Define processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if pretty_console and sys.stdout.isatty():
        # Pretty console output for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(
                colors=True,
                exception_formatter=structlog.dev.plain_traceback
            )
        ]
    else:
        # JSON output for production
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    return structlog.get_logger()


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """
    Get a logger instance with optional name binding.

    Args:
        name: Optional logger name to bind

    Returns:
        Configured logger instance
    """
    logger = structlog.get_logger()
    if name:
        logger = logger.bind(logger_name=name)
    return logger


# Default logger instance
logger = get_logger("elvagent")

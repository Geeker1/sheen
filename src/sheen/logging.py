import logging
import sys

import structlog

from sheen.config import get_settings


def configure_logging() -> None:
    """Log as JSON in containers and as readable text in a terminal.

    Values such as run_id or request_id are attached once and then appear on
    every log line.
    """
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if get_settings().log_json and not sys.stderr.isatty()
        else structlog.dev.ConsoleRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )

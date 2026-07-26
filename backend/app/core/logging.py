"""Tier 2 #26: structured JSON logging via structlog.

Every log line is rendered as one JSON object on stdout, so logs are machine-
parseable and shippable to any log aggregator. A `request_id` contextvar is
propagated into every line by `RequestContextMiddleware` (app/main.py), so all
logs from one request share an ID - including stdlib logs from uvicorn, which
are routed through the same renderer via `ProcessorFormatter`.

`configure_logging()` is idempotent and called at import; safe to re-call.
"""
from __future__ import annotations

import logging
import sys

import structlog

_configured = False


def _request_id_processor(_logger, _method_name, event_dict):
    """Inject the current request_id contextvar into every structlog line."""
    from app.core.observability import request_id_var

    rid = request_id_var.get()
    if rid:
        event_dict["request_id"] = rid
    return event_dict


def configure_logging(level: str = "info") -> None:
    """Configure structlog + stdlib logging for JSON output. Idempotent."""
    global _configured
    if _configured:
        return
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _request_id_processor,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    structlog.configure(
        processors=shared_processors + [structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Route stdlib log records (uvicorn.access / uvicorn.error / our services)
    # through structlog's JSON renderer so the whole stream is uniform.
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(log_level)

    _configured = True


def get_logger(name: str | None = None):
    """Return a structlog bound logger. Configures logging on first use."""
    configure_logging()
    return structlog.get_logger(name)

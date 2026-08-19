"""
Structured application logging.

Provides a single `configure_logging()` entry point and a `get_logger()`
helper. Log records are emitted as single-line JSON so they are easy to
ingest into any log aggregator. Sensitive fields (API keys, passwords)
are never logged - callers must never pass them as log fields.
"""
import json
import logging
import sys
import time
from typing import Any

_SENSITIVE_KEYS = {"api_key", "password", "authorization", "token", "secret"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra = getattr(record, "extra_fields", None)
        if extra:
            for k, v in extra.items():
                if k.lower() in _SENSITIVE_KEYS:
                    continue
                payload[k] = v
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    root = logging.getLogger()
    root.setLevel(level.upper())
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)

    # Quiet down noisy third-party loggers a bit.
    logging.getLogger("uvicorn.access").setLevel("WARNING")
    logging.getLogger("sqlalchemy.engine").setLevel("WARNING")


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_with_fields(logger: logging.Logger, level: str, message: str, **fields: Any) -> None:
    """Log a message with structured extra fields, filtering sensitive keys."""
    logger.log(getattr(logging, level.upper(), logging.INFO), message, extra={"extra_fields": fields})

"""
SentinelAI Logging
==================

Structured JSON logging (or coloured text for the CLI). Anything passed via
``logger.info(msg, extra={...})`` is emitted as first-class JSON fields, and a
per-request ``request_id`` is attached to every record through a context var.
"""

from __future__ import annotations

import copy
import json
import logging
import sys
import traceback
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

# Attributes every LogRecord carries - everything else came from ``extra=``.
_STD_ATTRS = set(logging.LogRecord("x", 0, "x", 0, "", (), None).__dict__) | {"message", "asctime", "request_id"}
_HANDLER_TAG = "_sentinelai_handler"


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = getattr(record, "request_id", None)
        if request_id:
            data["request_id"] = request_id
        for key, value in record.__dict__.items():
            if key not in _STD_ATTRS and not key.startswith("_"):
                data[key] = value
        if record.exc_info and record.exc_info[0]:
            data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info),
            }
        return json.dumps(data, default=str)


class ColoredFormatter(logging.Formatter):
    COLORS = {
        "DEBUG": "\033[36m", "INFO": "\033[32m", "WARNING": "\033[33m",
        "ERROR": "\033[31m", "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Work on a copy: mutating the shared record leaks ANSI codes into other handlers.
        clone = copy.copy(record)
        clone.levelname = f"{self.COLORS.get(record.levelname, '')}{record.levelname}{self.RESET}"
        return super().format(clone)


def setup_logging(log_level: str = "INFO", log_format: str = "json", log_file: Optional[str] = None) -> None:
    """Configure the root logger. Safe to call repeatedly."""
    level = getattr(logging, str(log_level).upper(), logging.INFO)
    root = logging.getLogger()
    root.setLevel(level)
    for handler in [h for h in root.handlers if getattr(h, _HANDLER_TAG, False)]:
        root.removeHandler(handler)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.addFilter(RequestContextFilter())
    console.setFormatter(
        JSONFormatter() if log_format == "json" else ColoredFormatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )
    )
    setattr(console, _HANDLER_TAG, True)
    root.addHandler(console)

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path)
        file_handler.setLevel(level)
        file_handler.addFilter(RequestContextFilter())
        file_handler.setFormatter(JSONFormatter())
        setattr(file_handler, _HANDLER_TAG, True)
        root.addHandler(file_handler)

    for noisy in ("httpx", "httpx2", "httpcore", "urllib3", "asyncio", "aiosqlite"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Logger namespaced under ``sentinelai`` (never double-prefixed)."""
    return logging.getLogger(name if name.split(".")[0] == "sentinelai" else f"sentinelai.{name}")

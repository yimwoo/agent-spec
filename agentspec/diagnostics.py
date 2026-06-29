"""Structured diagnostic logging configuration for AgentSpec commands."""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import TextIO

from .policy import redact_sensitive_text


DIAGNOSTIC_LOG_SCHEMA = "agentspec.diagnostic_log.v0"
LOGGER_NAME = "agentspec"
_HANDLER_MARKER = "_agentspec_diagnostic_handler"
_DISABLED_LEVEL = logging.CRITICAL + 1


def get_logger() -> logging.Logger:
    """Return the shared AgentSpec diagnostic logger."""

    return logging.getLogger(LOGGER_NAME)


def configure_diagnostics(
    env: Mapping[str, str | None],
    *,
    stream: TextIO | None = None,
) -> logging.Logger:
    """Configure AgentSpec diagnostics from explicit environment controls."""

    logger = get_logger()
    _remove_diagnostic_handlers(logger)
    logger.propagate = False

    level_name = str(env.get("ASPEC_LOG_LEVEL") or "").strip().upper()
    if not level_name:
        logger.setLevel(_DISABLED_LEVEL)
        return logger
    level = _level_for_name(level_name)
    if level is None:
        logger.setLevel(_DISABLED_LEVEL)
        return logger

    log_format = str(env.get("ASPEC_LOG_FORMAT") or "text").strip().lower()
    formatter: logging.Formatter
    if log_format == "json":
        formatter = _JsonDiagnosticFormatter()
    else:
        formatter = _TextDiagnosticFormatter()

    log_file = str(env.get("ASPEC_LOG_FILE") or "").strip()
    if log_file:
        Path(log_file).parent.mkdir(parents=True, exist_ok=True)
        handler: logging.Handler = logging.FileHandler(log_file, encoding="utf-8")
    else:
        handler = logging.StreamHandler(stream if stream is not None else sys.stderr)
    setattr(handler, _HANDLER_MARKER, True)
    handler.setLevel(level)
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.setLevel(level)
    return logger


def _level_for_name(level_name: str) -> int | None:
    levels = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "WARN": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    return levels.get(level_name)


def _remove_diagnostic_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()


class _TextDiagnosticFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = redact_sensitive_text(record.getMessage())
        return f"{record.levelname} {record.name}: {message}"


class _JsonDiagnosticFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "schema": DIAGNOSTIC_LOG_SCHEMA,
            "level": record.levelname,
            "logger": record.name,
            "message": redact_sensitive_text(record.getMessage()),
        }
        return json.dumps(payload, sort_keys=False)

# src/observability/logger.py
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Optional


def get_run_logger(run_id: str) -> logging.Logger:
    return logging.getLogger(f"daily-sports-page.run.{run_id}")


def configure_logging(level: str = "INFO", log_file: Optional[str] = None) -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    try:
        from pythonjsonlogger import jsonlogger  # type: ignore

        formatter = jsonlogger.JsonFormatter()
    except ImportError:
        formatter = logging.Formatter("%(message)s")

    for h in handlers:
        h.setFormatter(formatter)
        root.addHandler(h)


def _log_structured(logger: logging.Logger, data: dict) -> None:
    """Log a structured dict as JSON string."""
    logger.info(json.dumps(data))


def log_run_start(logger: logging.Logger, run_id: str, edition_id: str) -> None:
    _log_structured(
        logger,
        {
            "event": "run_start",
            "run_id": run_id,
            "edition_id": edition_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def log_phase_complete(
    logger: logging.Logger,
    run_id: str,
    phase: str,
    duration_seconds: float,
    status: str,
) -> None:
    _log_structured(
        logger,
        {
            "event": "phase_complete",
            "run_id": run_id,
            "phase": phase,
            "duration_seconds": duration_seconds,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def log_run_complete(
    logger: logging.Logger,
    run: Any,
    published_url: Optional[str] = None,
) -> None:
    duration = None
    if hasattr(run, "started_at") and hasattr(run, "completed_at"):
        if run.started_at and run.completed_at:
            duration = (run.completed_at - run.started_at).total_seconds()

    _log_structured(
        logger,
        {
            "event": "run_complete",
            "run_id": getattr(run, "run_id", None),
            "edition_id": getattr(run, "edition_id", None),
            "final_status": str(getattr(run, "final_status", None)),
            "total_duration_seconds": duration,
            "published_url": published_url,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )


def log_run_failed(logger: logging.Logger, run_id: str, phase: str, error: str) -> None:
    _log_structured(
        logger,
        {
            "event": "run_failed",
            "run_id": run_id,
            "phase": phase,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

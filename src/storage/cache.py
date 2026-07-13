# src/storage/cache.py
from __future__ import annotations
import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


class ResponseCache:
    """Filesystem cache for raw provider responses."""

    def __init__(self, cache_dir: Path) -> None:
        self._dir = cache_dir
        self._dir.mkdir(parents=True, exist_ok=True)

    def get(self, key: str, max_age_seconds: int) -> dict | None:
        """Return cached data if it exists and is within max_age. None otherwise."""
        path = self._dir / f"{key}.json"
        if not path.exists():
            return None
        age = time.time() - path.stat().st_mtime
        if age > max_age_seconds:
            logger.info("cache miss (stale, %.0fs old): %s", age, key)
            return None
        logger.info("cache hit (%.0fs old): %s", age, key)
        return json.loads(path.read_text())

    def set(self, key: str, data: dict) -> None:
        """Write data to cache."""
        path = self._dir / f"{key}.json"
        path.write_text(json.dumps(data, indent=2))

    def clear(self, key: str) -> None:
        path = self._dir / f"{key}.json"
        if path.exists():
            path.unlink()

    def exists(self, key: str) -> bool:
        return (self._dir / f"{key}.json").exists()

    def age_seconds(self, key: str) -> float | None:
        path = self._dir / f"{key}.json"
        if not path.exists():
            return None
        return time.time() - path.stat().st_mtime

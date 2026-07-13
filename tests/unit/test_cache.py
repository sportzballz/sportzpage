# tests/unit/test_cache.py
import json
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from src.storage.cache import ResponseCache


SAMPLE_DATA = {"games": [{"id": 1, "home": "NYY", "away": "BOS"}]}


class TestResponseCacheSetAndGet:
    def test_set_and_get_within_max_age_returns_data(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path)
        cache.set("schedule_2026-07-13", SAMPLE_DATA)
        result = cache.get("schedule_2026-07-13", max_age_seconds=3600)
        assert result == SAMPLE_DATA

    def test_get_after_max_age_returns_none(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path)
        cache.set("schedule_2026-07-13", SAMPLE_DATA)
        # Backdate the file's mtime by 2 hours
        path = tmp_path / "schedule_2026-07-13.json"
        old_mtime = time.time() - 7200
        import os

        os.utime(path, (old_mtime, old_mtime))
        result = cache.get("schedule_2026-07-13", max_age_seconds=300)
        assert result is None

    def test_get_missing_key_returns_none(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path)
        result = cache.get("nonexistent_key", max_age_seconds=3600)
        assert result is None

    def test_get_at_exact_max_age_boundary_returns_data(self, tmp_path: Path) -> None:
        """Data written just under max_age threshold should be returned."""
        cache = ResponseCache(tmp_path)
        cache.set("schedule_2026-07-13", SAMPLE_DATA)
        # Backdate by exactly (max_age - 1) seconds
        path = tmp_path / "schedule_2026-07-13.json"
        near_threshold_mtime = time.time() - 299
        import os

        os.utime(path, (near_threshold_mtime, near_threshold_mtime))
        result = cache.get("schedule_2026-07-13", max_age_seconds=300)
        assert result == SAMPLE_DATA


class TestResponseCacheClear:
    def test_clear_removes_file(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path)
        cache.set("standings_2026-07-13", SAMPLE_DATA)
        assert (tmp_path / "standings_2026-07-13.json").exists()
        cache.clear("standings_2026-07-13")
        assert not (tmp_path / "standings_2026-07-13.json").exists()

    def test_clear_nonexistent_key_does_not_raise(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path)
        # Should be a no-op
        cache.clear("does_not_exist")


class TestResponseCacheExists:
    def test_exists_returns_true_for_written_key(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path)
        cache.set("injuries_2026-07-13", SAMPLE_DATA)
        assert cache.exists("injuries_2026-07-13") is True

    def test_exists_returns_false_for_missing_key(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path)
        assert cache.exists("never_written") is False

    def test_exists_returns_false_after_clear(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path)
        cache.set("transactions_2026-07-13", SAMPLE_DATA)
        cache.clear("transactions_2026-07-13")
        assert cache.exists("transactions_2026-07-13") is False


class TestResponseCacheAgeSeconds:
    def test_age_seconds_returns_float_for_existing_key(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path)
        cache.set("schedule_2026-07-13", SAMPLE_DATA)
        age = cache.age_seconds("schedule_2026-07-13")
        assert age is not None
        assert isinstance(age, float)
        assert 0.0 <= age < 5.0  # Written moments ago

    def test_age_seconds_returns_none_for_missing_key(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path)
        assert cache.age_seconds("nonexistent") is None

    def test_age_seconds_reflects_backdated_mtime(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path)
        cache.set("old_data", SAMPLE_DATA)
        path = tmp_path / "old_data.json"
        old_mtime = time.time() - 3600
        import os

        os.utime(path, (old_mtime, old_mtime))
        age = cache.age_seconds("old_data")
        assert age is not None
        assert 3599.0 <= age <= 3601.0


class TestResponseCacheInit:
    def test_init_creates_directory(self, tmp_path: Path) -> None:
        nested = tmp_path / "a" / "b" / "c"
        assert not nested.exists()
        ResponseCache(nested)
        assert nested.exists()

    def test_set_writes_valid_json(self, tmp_path: Path) -> None:
        cache = ResponseCache(tmp_path)
        cache.set("my_key", {"foo": "bar", "n": 42})
        path = tmp_path / "my_key.json"
        parsed = json.loads(path.read_text())
        assert parsed == {"foo": "bar", "n": 42}

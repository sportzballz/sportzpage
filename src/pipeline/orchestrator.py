# src/pipeline/orchestrator.py
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import date, datetime, timezone
from pathlib import Path

from src.collectors.mlb import MLBCollector
from src.config import load_settings
from src.editorial.engine import EditorialEngine
from src.models.run import GenerationRun, PhaseStatus, RunStatus
from src.normalization.normalizer import Normalizer
from src.publishing.publisher import Publisher, PublicationError
from src.rendering.renderer import render_from_file
from src.validation.validator import ContentValidator

logger = logging.getLogger(__name__)

LOCK_TIMEOUT_SECONDS = 600


class PipelineLock:
    """File-based mutex to prevent concurrent pipeline runs."""

    def __init__(self, lock_path: Path, timeout_seconds: int = LOCK_TIMEOUT_SECONDS) -> None:
        self._path = lock_path
        self._timeout = timeout_seconds

    def acquire(self) -> bool:
        if self._path.exists():
            try:
                mtime = self._path.stat().st_mtime
                if time.time() - mtime < self._timeout:
                    logger.warning("pipeline lock held by another process (lock: %s)", self._path)
                    return False
                logger.warning("stale lock detected, removing: %s", self._path)
            except OSError:
                pass
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(str(os.getpid()))
        return True

    def release(self) -> None:
        if self._path.exists():
            self._path.unlink(missing_ok=True)


class GenerationOrchestrator:
    """Wires all pipeline stages and manages run state and degraded modes."""

    def __init__(
        self,
        build_dir: Path,
        publish_root: Path,
        archive_root: Path,
        game_date: date,
        dry_run: bool = False,
    ) -> None:
        self._build_dir = build_dir
        self._publish_root = publish_root
        self._archive_root = archive_root
        self._game_date = game_date
        self._dry_run = dry_run
        self._settings = load_settings()

    async def run(self, edition_json_override: Path | None = None) -> GenerationRun:
        """Execute the full pipeline."""
        lock = PipelineLock(self._publish_root / ".pipeline.lock")
        if not lock.acquire():
            run = GenerationRun.start()
            run.complete(RunStatus.failed, error="Concurrent pipeline run detected, aborting.")
            return run

        run = GenerationRun.start()
        try:
            if edition_json_override:
                edition_path = edition_json_override
            else:
                raw = await self._collect(run)
                edition_path = await self._normalize(raw, run)
                edition_path = await self._generate(edition_path, run)

            await self._validate(edition_path, run)
            html_dir = await self._render(edition_path, run)

            if not self._dry_run:
                await self._publish(html_dir, run)
                run.complete(RunStatus.published)
            else:
                logger.info("dry run: skipping publish, output at %s", html_dir)
                run.complete(RunStatus.published)

        except Exception as exc:
            logger.exception("pipeline failed: %s", exc)
            run.complete(RunStatus.failed, error=str(exc))
        finally:
            lock.release()
            self._save_run_log(run)

        return run

    async def _collect(self, run: GenerationRun) -> dict:
        run.record_phase("collecting", PhaseStatus.in_progress)
        from src.storage.cache import ResponseCache

        cache = ResponseCache(self._build_dir / "cache")
        collector = MLBCollector(
            game_date=self._game_date,
            cache=cache,
            timeout=self._settings.mlb_api.timeout_seconds,
            max_attempts=self._settings.mlb_api.max_attempts,
            backoff_min=self._settings.mlb_api.backoff_min_seconds,
            backoff_max=self._settings.mlb_api.backoff_max_seconds,
        )
        raw = await collector.collect()
        # Save raw files for debugging and reruns
        raw_dir = self._build_dir / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        for key, data in raw.items():
            (raw_dir / f"{key}.json").write_text(json.dumps(data, indent=2))
        run.record_phase("collecting", PhaseStatus.completed)
        return raw

    async def _normalize(self, raw: dict, run: GenerationRun) -> Path:
        run.record_phase("normalizing", PhaseStatus.in_progress)
        normalizer = Normalizer()
        normalized = normalizer.normalize(raw)
        out = self._build_dir / "normalized.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(normalized.model_dump_json(indent=2))
        run.record_phase("normalizing", PhaseStatus.completed)
        return out

    async def _generate(self, normalized_path: Path, run: GenerationRun) -> Path:
        run.record_phase("generating", PhaseStatus.in_progress)
        engine = EditorialEngine.from_config()
        edition = await engine.generate(normalized_path)
        run.game_count = len(edition.games)
        run.story_count = len(edition.game_recaps) + len(edition.secondary_stories)
        run.leader_category_count = (
            len(edition.league_leaders.batting) + len(edition.league_leaders.pitching)
            if edition.league_leaders
            else 0
        )
        out = self._build_dir / "edition.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(edition.model_dump_json(indent=2))
        run.record_phase("generating", PhaseStatus.completed)
        return out

    async def _validate(self, edition_path: Path, run: GenerationRun) -> None:
        run.record_phase("validating", PhaseStatus.in_progress)
        validator = ContentValidator()
        report = validator.validate_edition_file(edition_path)
        if report.has_errors:
            run.record_phase("validating", PhaseStatus.failed, report.summary())
            raise ValueError(f"Edition validation failed: {report.summary()}")
        run.record_phase("validating", PhaseStatus.completed)

    async def _render(self, edition_path: Path, run: GenerationRun) -> Path:
        run.record_phase("rendering", PhaseStatus.in_progress)
        html_path = render_from_file(edition_path, self._build_dir)
        run.record_phase("rendering", PhaseStatus.completed)
        return html_path.parent

    async def _publish(self, build_dir: Path, run: GenerationRun) -> None:
        run.record_phase("publishing", PhaseStatus.in_progress)
        publisher = Publisher(
            publish_root=self._publish_root,
            archive_root=self._archive_root,
            last_known_good_path=self._publish_root / "index.html.lkg",
            cdn_purge_hook=self._settings.cdn_purge_hook,
        )
        edition_id_raw = (
            self._build_dir.name
            if self._build_dir.name != "build"
            else datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
        )
        publisher.publish(build_dir, edition_id_raw)
        run.published_url = f"{self._settings.public_base_url}/index.html"
        run.record_phase("publishing", PhaseStatus.completed)

    def _save_run_log(self, run: GenerationRun) -> None:
        try:
            self._build_dir.mkdir(parents=True, exist_ok=True)
            (self._build_dir / "run.json").write_text(run.model_dump_json(indent=2))
        except Exception as exc:
            logger.warning("failed to save run log: %s", exc)

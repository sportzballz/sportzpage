# src/cli.py
"""SportzBallz Daily Sports Page — command-line interface."""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import typer

app = typer.Typer(
    name="daily-sports-page",
    help="SportzBallz Daily Sports Page generation pipeline.",
    add_completion=False,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)


def _syncify(coro):  # type: ignore[no-untyped-def]
    """Run an async coroutine from a synchronous Typer callback."""
    return asyncio.run(coro)


def _resolve_date(date_str: str | None) -> date:
    if date_str is None:
        return date.today()
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        typer.echo(f"ERROR: Invalid date '{date_str}'. Expected YYYY-MM-DD.", err=True)
        raise typer.Exit(1)


def _build_dir_from_settings(build_override: str | None = None) -> Path:
    from src.config import load_settings

    settings = load_settings()
    return Path(build_override or settings.build_dir)


def _publisher_from_settings(
    publish_root_override: str | None = None,
    archive_root_override: str | None = None,
):  # type: ignore[return]
    from src.config import load_settings
    from src.publishing.publisher import Publisher

    settings = load_settings()
    return Publisher(
        publish_root=Path(publish_root_override or settings.publish_root),
        archive_root=Path(archive_root_override or settings.archive_root),
        last_known_good_path=Path(settings.publish_root) / settings.last_known_good_filename,
        cdn_purge_hook=settings.cdn_purge_hook,
    )


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------


@app.command()
def collect(
    date_str: Optional[str] = typer.Option(None, "--date", "-d", help="Game date (YYYY-MM-DD)."),
    output_dir: Optional[str] = typer.Option(
        None, "--output-dir", "-o", help="Raw output directory."
    ),
) -> None:
    """Collect raw data from MLB Stats API and write to disk."""
    game_date = _resolve_date(date_str)
    build = _build_dir_from_settings(output_dir)

    async def _run() -> None:
        from src.collectors.mlb import MLBCollector
        from src.config import load_settings
        from src.storage.cache import ResponseCache
        import json

        settings = load_settings()
        cache = ResponseCache(build / "cache")
        collector = MLBCollector(
            game_date=game_date,
            cache=cache,
            timeout=settings.mlb_api.timeout_seconds,
            max_attempts=settings.mlb_api.max_attempts,
            backoff_min=settings.mlb_api.backoff_min_seconds,
            backoff_max=settings.mlb_api.backoff_max_seconds,
        )
        raw = await collector.collect()
        raw_dir = build / "raw"
        raw_dir.mkdir(parents=True, exist_ok=True)
        for key, data in raw.items():
            (raw_dir / f"{key}.json").write_text(json.dumps(data, indent=2))
        typer.echo(f"Collected {len(raw)} endpoints → {raw_dir}")

    try:
        _syncify(_run())
    except Exception as exc:
        typer.echo(f"ERROR: collect failed — {exc}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# normalize
# ---------------------------------------------------------------------------


@app.command()
def normalize(
    raw_dir: Optional[str] = typer.Option(
        None, "--raw-dir", help="Directory containing raw JSON files."
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output path for normalized.json."
    ),
) -> None:
    """Normalize raw collected data to domain models."""
    import json

    from src.normalization.normalizer import Normalizer

    build = _build_dir_from_settings()
    src_dir = Path(raw_dir) if raw_dir else build / "raw"
    dest = Path(output) if output else build / "normalized.json"

    if not src_dir.exists():
        typer.echo(f"ERROR: raw directory not found: {src_dir}", err=True)
        raise typer.Exit(1)

    raw: dict = {}
    for f in src_dir.glob("*.json"):
        raw[f.stem] = json.loads(f.read_text())

    try:
        normalizer = Normalizer()
        normalized = normalizer.normalize(raw)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(normalized.model_dump_json(indent=2))
        typer.echo(f"Normalized → {dest}")
    except Exception as exc:
        typer.echo(f"ERROR: normalize failed — {exc}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------


@app.command()
def generate(
    normalized_path: Optional[str] = typer.Option(
        None, "--normalized", "-n", help="Path to normalized.json."
    ),
    output: Optional[str] = typer.Option(
        None, "--output", "-o", help="Output path for edition.json."
    ),
) -> None:
    """Run the editorial engine to generate an Edition JSON."""
    build = _build_dir_from_settings()
    src_path = Path(normalized_path) if normalized_path else build / "normalized.json"
    dest = Path(output) if output else build / "edition.json"

    if not src_path.exists():
        typer.echo(f"ERROR: normalized.json not found: {src_path}", err=True)
        raise typer.Exit(1)

    async def _run() -> None:
        from src.editorial.engine import EditorialEngine

        engine = EditorialEngine.from_config()
        edition = await engine.generate(src_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(edition.model_dump_json(indent=2))
        typer.echo(f"Edition generated → {dest}")

    try:
        _syncify(_run())
    except Exception as exc:
        typer.echo(f"ERROR: generate failed — {exc}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


@app.command()
def validate(
    edition_json: str = typer.Argument(..., help="Path to edition.json."),
    strict: bool = typer.Option(False, "--strict", help="Exit 1 on warnings as well as errors."),
) -> None:
    """Validate an Edition JSON file for schema and content integrity."""
    from src.validation.validator import ContentValidator

    path = Path(edition_json)
    if not path.exists():
        typer.echo(f"ERROR: file not found: {path}", err=True)
        raise typer.Exit(1)

    try:
        validator = ContentValidator()
        report = validator.validate_edition_file(path)
    except Exception as exc:
        typer.echo(f"ERROR: validation raised an exception — {exc}", err=True)
        raise typer.Exit(1)

    if report.errors:
        for e in report.errors:
            typer.echo(f"  ERROR: {e}", err=True)
    if report.warnings:
        for w in report.warnings:
            typer.echo(f"  WARNING: {w}")

    if report.has_errors:
        typer.echo(f"Validation FAILED — {report.summary()}", err=True)
        raise typer.Exit(1)
    if strict and report.warnings:
        typer.echo(f"Validation FAILED (strict) — {report.summary()}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Validation passed — {report.summary()}")


# ---------------------------------------------------------------------------
# render
# ---------------------------------------------------------------------------


@app.command()
def render(
    edition_json: Optional[str] = typer.Option(
        None, "--edition", "-e", help="Path to edition.json."
    ),
    output_dir: Optional[str] = typer.Option(None, "--output-dir", "-o", help="Output directory."),
) -> None:
    """Render edition.json to index.html."""
    from src.rendering.renderer import render_from_file

    build = _build_dir_from_settings()
    src_path = Path(edition_json) if edition_json else build / "edition.json"
    out_dir = Path(output_dir) if output_dir else build

    if not src_path.exists():
        typer.echo(f"ERROR: edition.json not found: {src_path}", err=True)
        raise typer.Exit(1)

    try:
        html_path = render_from_file(src_path, out_dir)
        typer.echo(f"Rendered → {html_path}")
    except Exception as exc:
        typer.echo(f"ERROR: render failed — {exc}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------


@app.command()
def publish(
    build_dir: Optional[str] = typer.Argument(None, help="Build directory to publish from."),
    rollback: bool = typer.Option(False, "--rollback", help="Rollback to last-known-good edition."),
) -> None:
    """Publish a pre-built edition to the CDN origin, or rollback to last-known-good."""
    from src.publishing.publisher import PublicationError

    publisher = _publisher_from_settings()

    if rollback:
        try:
            publisher.rollback()
            typer.echo("Rollback complete.")
        except PublicationError as exc:
            typer.echo(f"ERROR: rollback failed — {exc}", err=True)
            raise typer.Exit(1)
        return

    build = Path(build_dir) if build_dir else _build_dir_from_settings()
    if not build.exists():
        typer.echo(f"ERROR: build directory not found: {build}", err=True)
        raise typer.Exit(1)

    from datetime import timezone

    edition_id = (
        build.name
        if build.name != "build"
        else datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")
    )

    try:
        publisher.publish(build, edition_id)
        typer.echo(f"Published edition {edition_id}.")
    except PublicationError as exc:
        typer.echo(f"ERROR: publish failed — {exc}", err=True)
        raise typer.Exit(1)
    except Exception as exc:
        typer.echo(f"ERROR: unexpected error during publish — {exc}", err=True)
        raise typer.Exit(1)


# ---------------------------------------------------------------------------
# run  (full pipeline)
# ---------------------------------------------------------------------------


@app.command()
def run(
    date_str: Optional[str] = typer.Option(None, "--date", "-d", help="Game date (YYYY-MM-DD)."),
    edition_date_str: Optional[str] = typer.Option(
        None, "--edition-date", help="Publication date for the masthead (YYYY-MM-DD)."
    ),
    edition_json: Optional[str] = typer.Option(
        None,
        "--edition-json",
        help="Skip collect/normalize/generate; render and publish this edition.json.",
    ),
    edition_type: Optional[str] = typer.Option(
        None,
        "--edition-type",
        help="Edition type override (morning|midday|evening|late|final|special).",
    ),
    do_publish: bool = typer.Option(False, "--publish", help="Publish after generation."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Run full pipeline but skip the publish step."
    ),
    build_dir_override: Optional[str] = typer.Option(
        None, "--build-dir", help="Override the build directory."
    ),
) -> None:
    """Run the full generation pipeline (collect → normalize → generate → validate → render → publish)."""
    from src.config import load_settings
    from src.pipeline.orchestrator import GenerationOrchestrator

    settings = load_settings()
    game_date = _resolve_date(date_str)
    edition_date = _resolve_date(edition_date_str) if edition_date_str else None
    build = Path(build_dir_override) if build_dir_override else _build_dir_from_settings()
    edition_override = Path(edition_json) if edition_json else None

    if edition_override and not edition_override.exists():
        typer.echo(f"ERROR: edition-json not found: {edition_override}", err=True)
        raise typer.Exit(1)

    # dry_run wins if --publish not given
    effective_dry_run = dry_run or not do_publish

    orchestrator = GenerationOrchestrator(
        build_dir=build,
        publish_root=Path(settings.publish_root),
        archive_root=Path(settings.archive_root),
        game_date=game_date,
        edition_date=edition_date,
        dry_run=effective_dry_run,
    )

    async def _run() -> None:
        gen_run = await orchestrator.run(edition_json_override=edition_override)
        if gen_run.final_status in ("published", "published_degraded"):
            typer.echo(f"Pipeline complete — status: {gen_run.final_status}")
            if gen_run.published_url:
                typer.echo(f"  URL: {gen_run.published_url}")
        else:
            typer.echo(
                f"Pipeline FAILED — status: {gen_run.final_status}\n  {gen_run.error}", err=True
            )
            raise typer.Exit(1)

    try:
        _syncify(_run())
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"ERROR: pipeline raised an unexpected exception — {exc}", err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()

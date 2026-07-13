# Design: Daily Sports Page

A browser-based, newspaper-style MLB publication generated several times each day and published as static HTML to `https://sportzballz.io/daily-sports-page/index.html`. The generation pipeline runs on a configurable schedule (America/New_York), assembles structured baseball data into an Edition JSON document, feeds that document through an AI-assisted editorial layer, and renders it to a single static HTML file that is atomically published to the CDN origin.

---

## Context

This is a greenfield project. No existing codebase, no running service, no database. The repository does not yet exist — this design establishes every architectural decision from scratch.

The publication model is intentionally old-fashioned: a static HTML page generated in bulk, readable without JavaScript, structured like a newspaper. The generation pipeline handles all data assembly, validation, editorial selection, and rendering offline. The CDN serves the result. There is no runtime server.

No `docs/dev/architecture.md` exists in the project. This design document is the primary architectural record.

---

## References

- [Pydantic v2 docs](https://docs.pydantic.dev/latest/) — Defines the v2 model API, `Field`, `model_validator`, and `model_rebuild` patterns used throughout this design.
- [Jinja2 docs](https://jinja.palletsprojects.com/en/3.1.x/) — Template engine for HTML rendering; covers environment configuration, autoescape, filters, and macro composition.
- [HTTPX docs](https://www.python-httpx.org/) — Async HTTP client used for all data provider requests; covers timeouts, retries (via Tenacity), and connection pooling.
- [Tenacity docs](https://tenacity.readthedocs.io/en/latest/) — Retry library used with HTTPX; covers `wait_exponential`, `stop_after_attempt`, and `retry_if_exception_type`.
- [Typer docs](https://typer.tiangolo.com/) — CLI framework; covers command definitions, `Annotated` arguments and options, and exit codes.
- [Playwright Python docs](https://playwright.dev/python/) — Browser automation used for visual regression tests across multiple viewports.
- [BeautifulSoup docs](https://www.crummy.com/software/BeautifulSoup/bs4/doc/) — Used in validation only, not rendering; parses rendered HTML to verify required sections and escape correctness.
- [MLB Stats API (unofficial)](https://github.com/toddrob99/MLB-StatsAPI) — Community documentation for the MLB Stats API endpoints used for scores, standings, rosters, and transactions.
- [WCAG 2.1 AA](https://www.w3.org/TR/WCAG21/) — Accessibility standard; contrast ratios, keyboard navigation, and ARIA semantics requirements.

---

## Goals / Non-Goals

**Goals:**

- Full generation pipeline: collect → normalize → generate → validate → render → publish
- Pydantic v2 models for every data structure in the pipeline
- Edition JSON as the single decoupling layer between data logic and HTML rendering
- AI-assisted story generation with deterministic fallback templates
- Atomic publication to CDN origin with rollback to last-known-good
- Six edition types: morning, midday, evening, late, final, special
- All eight page sections with stable anchor IDs
- Configurable lead-story scoring with manual editorial override
- Configurable data freshness thresholds and retry behavior
- Structured observability: per-run status, phase timing, provider health
- Static HTML readable without JavaScript; JS enhances but does not gate content
- Accessibility: WCAG 2.1 AA, semantic HTML, keyboard navigation
- Performance budget: HTML < 500 KB, total page < 2 MB, LCP < 2.5 s
- `daily-sports-page` Typer CLI with `collect`, `normalize`, `generate`, `validate`, `render`, `publish`, and `run` commands

**Non-Goals:**

- Native mobile or desktop applications
- User accounts, authentication, or personalization
- Runtime server or client-side API calls for core content
- A persistent relational database for page viewing
- Per-user subscriptions, newsletters, or push notifications
- Live in-game score updates without a full pipeline re-run
- Team or player profile pages (this design covers only the daily index page)
- Video, audio, or large photography assets
- Comment sections or social features
- Paid content or paywalls

---

## Decisions

### D1: Python as the primary generation pipeline language

**Decision:** The generation pipeline is written in Python 3.12+. All data collection, normalization, statistical processing, editorial logic, AI integration, Jinja2 rendering, and publication are Python. Node.js is optional and limited to CSS/JS asset builds (PostCSS, esbuild, Prettier, HTMLHint) invoked as subprocesses by the pipeline.

```python
# src/pipeline/runner.py
import subprocess
from pathlib import Path


def build_frontend_assets(static_dir: Path) -> None:
    """Invoke Node.js asset build as a subprocess. Optional — skipped if node is not present."""
    node_bin = Path("node_modules/.bin")
    if not (node_bin / "esbuild").exists():
        return
    subprocess.run(
        [
            str(node_bin / "esbuild"),
            str(static_dir / "js" / "main.js"),
            "--bundle",
            "--minify",
            "--outfile",
            str(static_dir / "js" / "main.min.js"),
        ],
        check=True,
    )
```

**Alternative considered:** Node.js as the primary language with a JS SSG (Eleventy, Astro). Rejected — the pipeline is data-heavy Python (Pydantic, Tenacity, statistics), and Python's ML/AI ecosystem integrates better with OpenAI/Anthropic SDKs. A full Node.js rewrite would not improve the output and would fragment the toolchain.

**Alternative considered:** Go for the pipeline. Rejected — excellent performance but poor AI SDK ecosystem and significantly more verbose for the data modeling and validation work that dominates this codebase.

---

### D2: Edition JSON as the decoupling layer

**Decision:** All business logic — data collection, normalization, statistical processing, editorial scoring, and AI story generation — runs before the renderer. The renderer is a pure function of a single Edition JSON document. This means `render --edition-json path/to/edition.json` can re-render any edition from disk without touching any data provider or AI service.

```python
# src/models/edition.py
from __future__ import annotations
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


EditionType = Literal["morning", "midday", "evening", "late", "final", "special"]
EditionStatus = Literal["draft", "generating", "validating", "published", "failed", "published_degraded"]


class EditionMetadata(BaseModel):
    """Top-level metadata identifying this edition."""
    id: str = Field(
        description="Edition ID in the form YYYY-MM-DD-HHMM, e.g. 2026-07-13-0600.",
        examples=["2026-07-13-0600"],
    )
    type: EditionType = Field(description="Edition type controlling content emphasis.")
    date: str = Field(description="Publication date in YYYY-MM-DD format.")
    generated_at: datetime = Field(description="ISO 8601 timestamp when generation completed.")
    data_current_through: datetime = Field(description="Latest data timestamp included in this edition.")
    timezone: str = Field(default="America/New_York", description="Display timezone for all times on the page.")
    status: EditionStatus = Field(description="Current lifecycle status of this edition.")
```

```python
# src/rendering/renderer.py
import json
from pathlib import Path
from src.models.edition import Edition
from src.rendering.html_renderer import HTMLRenderer


def render_from_file(edition_json_path: Path, output_dir: Path) -> Path:
    """Render HTML from an Edition JSON file. Pure function — no network, no AI."""
    raw = json.loads(edition_json_path.read_text(encoding="utf-8"))
    edition = Edition.model_validate(raw)
    renderer = HTMLRenderer.from_config()
    html = renderer.render(edition)
    out = output_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    return out
```

**Alternative considered:** Passing domain objects (Python model instances) directly from pipeline stages to the renderer. Rejected — this couples the renderer to the pipeline runtime. Edition JSON allows independent re-render, archiving, debugging, and A/B testing of templates without re-running expensive API calls.

---

### D3: Pydantic v2 models for all data structures

**Decision:** Every data structure that crosses a module boundary — raw API responses, normalized domain models, Edition JSON, run status, config — is a Pydantic v2 `BaseModel`. Validation happens at parse time. The pipeline never passes raw dicts between services.

```python
# src/models/game.py
from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class GameStatus(str, Enum):
    final = "final"
    in_progress = "in_progress"
    scheduled = "scheduled"
    postponed = "postponed"
    delayed = "delayed"
    suspended = "suspended"


class LinescoreInning(BaseModel):
    inning: int = Field(description="Inning number (1-indexed).")
    away_runs: int | None = Field(default=None, description="Runs scored by away team this inning.")
    home_runs: int | None = Field(default=None, description="Runs scored by home team this inning.")


class TeamGameLine(BaseModel):
    team_id: int = Field(description="MLB team ID.")
    team_abbr: str = Field(description="Team abbreviation, e.g. NYY.")
    team_name: str = Field(description="Full team name.")
    runs: int | None = Field(default=None, description="Runs scored. None if game not started.")
    hits: int | None = Field(default=None)
    errors: int | None = Field(default=None)


class Pitcher(BaseModel):
    player_id: int = Field(description="MLB player ID.")
    name: str = Field(description="Full player name.")
    handedness: str | None = Field(default=None, description="L or R.")
    status: str = Field(
        default="probable",
        description="probable or confirmed.",
        examples=["probable", "confirmed"],
    )
    wins: int | None = Field(default=None, description="Season wins at time of edition generation.")
    losses: int | None = Field(default=None)
    era: float | None = Field(default=None, description="Season ERA.")


class Game(BaseModel):
    """A single MLB game with all state needed to render scoreboard, schedule, and recap sections."""
    game_id: int = Field(description="MLB game PK.")
    game_date: str = Field(description="Game date in YYYY-MM-DD.")
    game_time_et: str | None = Field(default=None, description="Scheduled start time in ET, e.g. 7:05 PM.")
    status: GameStatus = Field(description="Current game state.")
    inning: int | None = Field(default=None, description="Current inning if in progress.")
    inning_state: str | None = Field(default=None, description="Top, Middle, Bottom, End.")
    home: TeamGameLine = Field(description="Home team line score.")
    away: TeamGameLine = Field(description="Away team line score.")
    linescore: list[LinescoreInning] = Field(default_factory=list)
    home_probable_pitcher: Pitcher | None = Field(default=None)
    away_probable_pitcher: Pitcher | None = Field(default=None)
    winning_pitcher: Pitcher | None = Field(default=None, description="Set when status is final.")
    losing_pitcher: Pitcher | None = Field(default=None)
    save_pitcher: Pitcher | None = Field(default=None)
    venue_name: str | None = Field(default=None)
    venue_city: str | None = Field(default=None)
    tv_broadcasts: list[str] = Field(default_factory=list, description="TV/streaming network names.")
    weather_description: str | None = Field(default=None, description="Short weather string for previews.")
    attendance: int | None = Field(
        default=None,
        description="Reported attendance. Never rendered for scheduled games — only final.",
    )
    is_doubleheader: bool = Field(default=False)
    doubleheader_game_num: int | None = Field(default=None, description="1 or 2.")
    tags: list[str] = Field(
        default_factory=list,
        description="Notable tags: walk-off, extra-inning, no-hitter, perfect-game, shutout, etc.",
    )
    series_description: str | None = Field(default=None, description="e.g. ALDS Game 3.")
```

**Alternative considered:** TypedDicts or dataclasses. Rejected — neither provides runtime validation, serialization/deserialization, or the IDE support that Pydantic v2 gives for free. Dataclasses require manual `__post_init__` validators that are error-prone and non-composable.

---

### D4: Jinja2 for HTML rendering

**Decision:** HTML is rendered by Jinja2 templates with `autoescape=True`. The renderer loads templates from `templates/`, passes the validated `Edition` model, and writes the result. No JavaScript SSG (Next.js, Astro, Eleventy) is involved in the HTML generation step.

```python
# src/rendering/html_renderer.py
import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape, StrictUndefined
from src.models.edition import Edition

logger = logging.getLogger(__name__)


class HTMLRenderer:
    """Renders a validated Edition to static HTML using Jinja2."""

    def __init__(self, templates_dir: Path, static_asset_manifest: dict[str, str]) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "j2"]),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._env.globals["asset"] = self._asset_url
        self._manifest = static_asset_manifest

    @classmethod
    def from_config(cls) -> "HTMLRenderer":
        from src.config import load_settings
        settings = load_settings()
        manifest_path = Path(settings.build_dir) / "asset-manifest.json"
        manifest: dict[str, str] = {}
        if manifest_path.exists():
            import json
            manifest = json.loads(manifest_path.read_text())
        return cls(templates_dir=Path("templates"), static_asset_manifest=manifest)

    def _asset_url(self, name: str) -> str:
        """Resolve a static asset to its versioned URL."""
        return self._manifest.get(name, f"/daily-sports-page/static/{name}")

    def render(self, edition: Edition) -> str:
        """Render the edition to an HTML string. No side effects."""
        template = self._env.get_template("index.html.j2")
        html = template.render(edition=edition)
        logger.info("rendered edition %s (%d bytes)", edition.edition.id, len(html.encode()))
        return html
```

```html
{# templates/index.html.j2 #}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SportzBallz Daily Sports Page — {{ edition.edition.date }}</title>
  <link rel="stylesheet" href="{{ asset('css/main.css') }}">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:;">
</head>
<body>
  {% include "sections/front-page.html.j2" %}
  {% include "sections/scoreboard.html.j2" %}
  {% include "sections/todays-games.html.j2" %}
  {% include "sections/standings.html.j2" %}
  {% include "sections/league-leaders.html.j2" %}
  {% include "sections/game-recaps.html.j2" %}
  {% include "sections/around-the-league.html.j2" %}
  {% include "sections/transactions.html.j2" %}
  {% include "sections/injuries.html.j2" %}
  {% include "sections/history.html.j2" %}
  <script src="{{ asset('js/main.min.js') }}"></script>
</body>
</html>
```

**Alternative considered:** Eleventy or Astro with JSON data files. Rejected — introduces a Node.js runtime dependency for the critical-path render step. Jinja2 runs in-process, is easily testable, and keeps the entire pipeline in a single Python environment.

**Alternative considered:** Python string templates or f-strings. Rejected — no autoescape, no inheritance, no macros, no partial include system.

---

### D5: HTTPX + Tenacity for data collection

**Decision:** All outbound HTTP calls use `httpx.AsyncClient` with per-provider timeouts. Retries are managed by Tenacity with exponential backoff. Each provider's base URL, timeout, and retry configuration is read from `config/settings.yaml`.

```python
# src/collectors/base.py
import logging
from abc import ABC, abstractmethod
from typing import Any
import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

logger = logging.getLogger(__name__)

RETRYABLE = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


class CollectorError(Exception):
    """Base exception for all collector failures."""


class ProviderUnavailableError(CollectorError):
    """Raised when a provider is unreachable after all retries."""


class Collector(ABC):
    """Base class for all data collectors."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
        max_attempts: int = 3,
        backoff_min: float = 1.0,
        backoff_max: float = 30.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._max_attempts = max_attempts
        self._backoff_min = backoff_min
        self._backoff_max = backoff_max

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Make a GET request with retry. Returns parsed JSON."""
        @retry(
            retry=retry_if_exception_type(RETRYABLE),
            stop=stop_after_attempt(self._max_attempts),
            wait=wait_exponential(min=self._backoff_min, max=self._backoff_max),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=False,
        )
        async def _attempt() -> Any:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(f"{self._base_url}{path}", params=params)
                response.raise_for_status()
                return response.json()

        try:
            return await _attempt()
        except Exception as exc:
            raise ProviderUnavailableError(
                f"Provider at {self._base_url}{path} unavailable after {self._max_attempts} attempts"
            ) from exc

    @abstractmethod
    async def collect(self) -> dict[str, Any]:
        """Collect all required data from this provider. Returns raw response dict."""
```

```python
# src/collectors/mlb.py
import logging
from datetime import date
from typing import Any
from src.collectors.base import Collector

logger = logging.getLogger(__name__)


class MLBCollector(Collector):
    """Collector for the MLB Stats API."""

    def __init__(self, game_date: date, **kwargs: Any) -> None:
        super().__init__(base_url="https://statsapi.mlb.com/api/v1", **kwargs)
        self._game_date = game_date

    async def get_schedule(self) -> Any:
        """Fetch full schedule for the target date including linescore."""
        return await self._get(
            "/schedule",
            params={
                "sportId": 1,
                "date": self._game_date.strftime("%m/%d/%Y"),
                "hydrate": "linescore,probablePitcher(note),broadcasts(all),decisions,weather",
            },
        )

    async def get_standings(self) -> Any:
        """Fetch current standings for all divisions."""
        return await self._get(
            "/standings",
            params={"leagueId": "103,104", "standingsType": "regularSeason"},
        )

    async def get_stats_leaders(self, stat_group: str, stat_type: str, season: int) -> Any:
        """Fetch league leaders for a single stat category."""
        return await self._get(
            "/stats/leaders",
            params={
                "leaderCategories": stat_type,
                "statGroup": stat_group,
                "season": season,
                "limit": 10,
                "sportId": 1,
            },
        )

    async def get_transactions(self) -> Any:
        """Fetch recent transactions."""
        date_str = self._game_date.strftime("%Y%m%d")
        return await self._get("/transactions", params={"date": date_str, "sportId": 1})

    async def get_injuries(self) -> Any:
        """Fetch current injury report."""
        return await self._get("/injuries", params={"sportId": 1})

    async def collect(self) -> dict[str, Any]:
        """Collect all data needed for an edition. Returns raw responses keyed by domain."""
        schedule = await self.get_schedule()
        standings = await self.get_standings()
        transactions = await self.get_transactions()
        injuries = await self.get_injuries()
        return {
            "schedule": schedule,
            "standings": standings,
            "transactions": transactions,
            "injuries": injuries,
        }
```

**Alternative considered:** `requests` (sync). Rejected — `httpx` provides async support with the same ergonomics, which allows concurrent provider calls to run in parallel.

**Alternative considered:** `aiohttp`. Rejected — `httpx` has a more consistent interface, built-in sync/async parity, and better default timeout handling.

---

### D6: Configurable lead-story scoring

**Decision:** Editorial significance is scored by a weighted formula. Weights are configured in `config/editorial.yaml`. Individual games or stories can be manually pinned to lead via the same config file.

```python
# src/editorial/scoring.py
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from src.models.game import Game

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """Weights for the lead-story scoring model. All values are floats."""
    playoff_weight: float = 3.0
    historic_weight: float = 2.5
    performance_weight: float = 2.0
    game_drama_weight: float = 1.5
    national_interest_weight: float = 1.0
    recency_weight: float = 0.5


@dataclass
class ScoringContext:
    """Contextual flags that inform scoring for a single game."""
    is_postseason: bool = False
    has_historic_performance: bool = False       # no-hitter, perfect game, cycle, etc.
    performance_score: float = 0.0               # normalized 0–1 based on runs, pitching dominance
    drama_score: float = 0.0                     # walk-off, extra innings, late-game comeback
    is_nationally_televised: bool = False
    is_large_market: bool = False
    recency_bonus: float = 0.0                   # 1.0 if game ended within past 2 hours


def score_game(
    game: Game,
    context: ScoringContext,
    weights: ScoringWeights,
    manual_overrides: dict[int, float],
) -> float:
    """
    Compute the lead-story score for a game.

    If a manual override is present for this game_id, it takes precedence.
    Otherwise the weighted formula applies.
    """
    if game.game_id in manual_overrides:
        score = manual_overrides[game.game_id]
        logger.info("game %d: manual override score %.2f", game.game_id, score)
        return score

    score = (
        (weights.playoff_weight if context.is_postseason else 0.0)
        + (weights.historic_weight if context.has_historic_performance else 0.0)
        + weights.performance_weight * context.performance_score
        + weights.game_drama_weight * context.drama_score
        + (weights.national_interest_weight if (context.is_nationally_televised or context.is_large_market) else 0.0)
        + weights.recency_weight * context.recency_bonus
    )
    logger.debug("game %d score: %.3f", game.game_id, score)
    return score
```

```yaml
# config/editorial.yaml
scoring_weights:
  playoff_weight: 3.0
  historic_weight: 2.5
  performance_weight: 2.0
  game_drama_weight: 1.5
  national_interest_weight: 1.0
  recency_weight: 0.5

manual_lead_overrides:
  # game_id: score
  # 748293: 10.0  # pin this game as lead story

large_market_teams:
  - NYY
  - NYM
  - LAD
  - CHC
  - BOS
  - SF
  - PHI
  - ATL
  - HOU
  - STL
```

**Alternative considered:** Hardcoded priority rules (postseason always leads, etc.). Rejected — inflexible. The configurable weights allow editorial staff to tune priorities without code changes.

---

### D7: Atomic publication via filesystem rename

**Decision:** Generation writes to a temp directory. After all validation passes, the final `index.html` and assets are moved atomically using a rename on the CDN origin filesystem. The previous edition is preserved as `last-known-good` for rollback.

```python
# src/publishing/publisher.py
import logging
import shutil
import time
from datetime import datetime
from pathlib import Path
from src.models.run import GenerationRun, RunPhase, RunStatus

logger = logging.getLogger(__name__)


class PublicationError(Exception):
    """Raised when publication cannot complete safely."""


class Publisher:
    """Atomically publishes a validated build directory to the CDN origin."""

    def __init__(
        self,
        publish_root: Path,
        archive_root: Path,
        last_known_good_path: Path,
        cdn_purge_hook: str | None = None,
    ) -> None:
        self._publish_root = publish_root
        self._archive_root = archive_root
        self._last_known_good = last_known_good_path
        self._cdn_purge_hook = cdn_purge_hook

    def publish(self, build_dir: Path, edition_id: str) -> None:
        """
        Atomically publish the build directory.

        Steps:
        1. Verify required files in build_dir
        2. Save current index.html as last-known-good
        3. Copy assets (versioned, safe to overwrite)
        4. Atomic rename of index.html
        5. Verify published file
        6. Purge CDN cache
        7. Archive edition
        """
        self._verify_build(build_dir)
        self._save_last_known_good()
        self._publish_assets(build_dir)
        self._atomic_publish_html(build_dir)
        self._verify_published()
        self._purge_cdn()
        self._archive(build_dir, edition_id)
        logger.info("edition %s published successfully", edition_id)

    def rollback(self) -> None:
        """Restore the last-known-good edition."""
        if not self._last_known_good.exists():
            raise PublicationError("No last-known-good edition available for rollback.")
        dest = self._publish_root / "index.html"
        shutil.copy2(self._last_known_good, dest)
        logger.warning("rolled back to last-known-good edition")

    def _verify_build(self, build_dir: Path) -> None:
        required = ["index.html"]
        for f in required:
            if not (build_dir / f).exists():
                raise PublicationError(f"Required file missing from build: {f}")

    def _save_last_known_good(self) -> None:
        live = self._publish_root / "index.html"
        if live.exists():
            shutil.copy2(live, self._last_known_good)

    def _publish_assets(self, build_dir: Path) -> None:
        assets_src = build_dir / "static"
        if assets_src.exists():
            shutil.copytree(assets_src, self._publish_root / "static", dirs_exist_ok=True)

    def _atomic_publish_html(self, build_dir: Path) -> None:
        src = build_dir / "index.html"
        dest = self._publish_root / "index.html"
        tmp = dest.with_suffix(".html.tmp")
        shutil.copy2(src, tmp)
        tmp.rename(dest)  # atomic on POSIX; near-atomic on Windows

    def _verify_published(self) -> None:
        published = self._publish_root / "index.html"
        if not published.exists():
            raise PublicationError("Published index.html not found after rename.")

    def _purge_cdn(self) -> None:
        if not self._cdn_purge_hook:
            return
        import subprocess
        try:
            subprocess.run([self._cdn_purge_hook], check=True, timeout=30)
        except Exception as exc:
            logger.warning("CDN purge failed (non-fatal): %s", exc)

    def _archive(self, build_dir: Path, edition_id: str) -> None:
        self._archive_root.mkdir(parents=True, exist_ok=True)
        archive_name = f"{edition_id}.html"
        dest = self._archive_root / archive_name
        shutil.copy2(build_dir / "index.html", dest)
        logger.info("archived edition to %s", dest)
```

**Alternative considered:** Direct overwrite of `index.html`. Rejected — a write failure mid-overwrite leaves a corrupt page live. The rename approach is atomic on POSIX filesystems.

**Alternative considered:** S3 `PUT` with versioning. This is a valid alternative for S3-backed origins and is supported by making `Publisher` extensible. The filesystem `rename` strategy is the default for VPS/bare-metal origins.

---

### D8: Deterministic fallback when AI is unavailable

**Decision:** When the AI provider is unavailable, times out, or produces content that fails validation, the pipeline uses deterministic Jinja2 templates to generate recaps and editorial summaries from structured data. The page still publishes with scores, standings, schedule, and stats — only the prose narrative is degraded.

```python
# src/editorial/fallback.py
from __future__ import annotations
from jinja2 import Environment, BaseLoader
from src.models.game import Game
from src.models.story import GameRecap

RECAP_TEMPLATE = """
{%- set winner = game.home if game.home.runs > game.away.runs else game.away -%}
{%- set loser = game.away if game.home.runs > game.away.runs else game.home -%}
The {{ winner.team_name }} defeated the {{ loser.team_name }}
{{ winner.runs }}–{{ loser.runs }}{% if "walk-off" in game.tags %} in walk-off fashion{% endif %}
{%- if "extra-inning" in game.tags %} in extra innings{% endif %}.
{% if game.winning_pitcher -%}
{{ game.winning_pitcher.name }} earned the win.
{%- endif %}
{% if game.save_pitcher -%}
{{ game.save_pitcher.name }} recorded the save.
{%- endif %}
"""

_env = Environment(loader=BaseLoader(), trim_blocks=True, lstrip_blocks=True)


def generate_fallback_recap(game: Game) -> GameRecap:
    """Generate a deterministic recap from game data without AI."""
    from src.models.story import GameRecap, StoryType
    winner = game.home if (game.home.runs or 0) > (game.away.runs or 0) else game.away
    loser = game.away if winner == game.home else game.home

    headline = f"{winner.team_name} {winner.runs}, {loser.team_name} {loser.runs}"
    body = _env.from_string(RECAP_TEMPLATE).render(game=game).strip()

    return GameRecap(
        headline=headline,
        deck=f"Final: {winner.team_abbr} {winner.runs}, {loser.team_abbr} {loser.runs}",
        byline="SportzBallz Staff",
        paragraphs=[body],
        source_data_references=[f"game:{game.game_id}"],
        story_type=StoryType.game_recap,
        teams=[game.home.team_abbr, game.away.team_abbr],
        players=[],
        facts_used=[],
        game_id=game.game_id,
        final_score=f"{winner.team_abbr} {winner.runs}, {loser.team_abbr} {loser.runs}",
        winning_pitcher=game.winning_pitcher,
        losing_pitcher=game.losing_pitcher,
        save_pitcher=game.save_pitcher,
        tags=game.tags,
        ai_generated=False,
    )
```

**Alternative considered:** Skipping recap sections entirely when AI is unavailable. Rejected — a page with no game recaps is a significantly degraded user experience. The deterministic fallback guarantees that scores and outcomes are always narrated, even without prose quality.

---

### D9: Separate pipeline stages

**Decision:** The pipeline has six discrete stages (`collect`, `normalize`, `generate`, `validate`, `render`, `publish`), each independently executable via CLI. Stage outputs are persisted to disk (`build/<edition-id>/`) so any stage can be re-run independently. This enables `render --edition-json` dry runs, partial retries, and debugging.

```
collect  → raw/<edition-id>/           (raw JSON responses, one file per provider)
normalize → normalized/<edition-id>/   (validated Pydantic models serialized to JSON)
generate  → edition/<edition-id>/      (edition.json — the complete Edition document)
validate  → validate/<edition-id>/     (validation report JSON)
render    → build/<edition-id>/        (index.html + copied static assets)
publish   → /daily-sports-page/        (atomic rename into live directory)
```

```python
# src/pipeline/orchestrator.py
import asyncio
import logging
from datetime import date
from pathlib import Path
from src.models.run import GenerationRun, RunStatus, PhaseStatus
from src.collectors.mlb import MLBCollector
from src.normalization.normalizer import Normalizer
from src.editorial.engine import EditorialEngine
from src.validation.validator import ContentValidator
from src.rendering.html_renderer import HTMLRenderer
from src.publishing.publisher import Publisher

logger = logging.getLogger(__name__)


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

    async def run(self, edition_json_override: Path | None = None) -> GenerationRun:
        """
        Execute the full pipeline.

        If edition_json_override is provided, skip collect/normalize/generate
        and render directly from the supplied Edition JSON.
        """
        run = GenerationRun.start()
        try:
            if edition_json_override:
                run.record_phase("render", PhaseStatus.skipped, "edition-json override")
                html_path = await self._render_only(edition_json_override, run)
            else:
                raw = await self._collect(run)
                normalized = await self._normalize(raw, run)
                edition_path = await self._generate(normalized, run)
                await self._validate(edition_path, run)
                html_path = await self._render(edition_path, run)

            if not self._dry_run:
                await self._publish(html_path, run)
            else:
                logger.info("dry run: skipping publish, output at %s", html_path)

            run.complete(RunStatus.published)
        except Exception as exc:
            logger.exception("pipeline failed: %s", exc)
            run.complete(RunStatus.failed, error=str(exc))
        return run

    async def _collect(self, run: GenerationRun) -> dict:
        run.record_phase("collecting", PhaseStatus.in_progress)
        collector = MLBCollector(game_date=self._game_date)
        raw = await collector.collect()
        run.record_phase("collecting", PhaseStatus.completed)
        return raw

    async def _normalize(self, raw: dict, run: GenerationRun) -> Path:
        run.record_phase("normalizing", PhaseStatus.in_progress)
        normalizer = Normalizer()
        normalized = normalizer.normalize(raw)
        out = self._build_dir / "normalized.json"
        out.write_text(normalized.model_dump_json(indent=2))
        run.record_phase("normalizing", PhaseStatus.completed)
        return out

    async def _generate(self, normalized_path: Path, run: GenerationRun) -> Path:
        run.record_phase("generating", PhaseStatus.in_progress)
        engine = EditorialEngine.from_config()
        edition = await engine.generate(normalized_path)
        out = self._build_dir / "edition.json"
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
        from src.rendering.renderer import render_from_file
        html_path = render_from_file(edition_path, self._build_dir)
        run.record_phase("rendering", PhaseStatus.completed)
        return html_path

    async def _render_only(self, edition_path: Path, run: GenerationRun) -> Path:
        return await self._render(edition_path, run)

    async def _publish(self, html_path: Path, run: GenerationRun) -> None:
        run.record_phase("publishing", PhaseStatus.in_progress)
        publisher = Publisher(
            publish_root=self._publish_root,
            archive_root=self._archive_root,
            last_known_good_path=self._publish_root / "index.html.lkg",
        )
        publisher.publish(html_path.parent, run.edition_id or "unknown")
        run.record_phase("publishing", PhaseStatus.completed)
```

**Alternative considered:** A monolithic `run()` function with no intermediate persistence. Rejected — makes debugging impossible, forces a full re-run on any failure, and prevents `render --edition-json` dry runs.

---

### D10: CLI with Typer

**Decision:** All pipeline operations are exposed via a `daily-sports-page` CLI built with Typer. Async commands use a `syncify` decorator. All arguments and options use `Annotated[T, typer.Argument(...)]` / `Annotated[T, typer.Option(...)]`. Errors exit with code 1.

```python
# src/cli.py
import asyncio
import logging
from datetime import date
from functools import wraps
from pathlib import Path
from typing import Annotated, Any

import typer

from src.config import load_settings

app = typer.Typer(name="daily-sports-page", help="SportzBallz Daily Sports Page generation pipeline.")
logger = logging.getLogger(__name__)


def syncify(f: Any) -> Any:
    """Wrap an async Typer command as synchronous."""
    @wraps(f)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        return asyncio.run(f(*args, **kwargs))
    return wrapper


@app.command(help="Collect raw data from MLB data providers.")
@syncify
async def collect(
    game_date: Annotated[str | None, typer.Option("--date", help="Date in YYYY-MM-DD. Defaults to today.")] = None,
    output_dir: Annotated[str | None, typer.Option("--output-dir", help="Directory for raw output files.")] = None,
) -> None:
    from src.collectors.mlb import MLBCollector
    import json
    settings = load_settings()
    target = date.fromisoformat(game_date) if game_date else date.today()
    out = Path(output_dir or settings.build_dir) / "raw"
    out.mkdir(parents=True, exist_ok=True)
    collector = MLBCollector(game_date=target)
    try:
        raw = await collector.collect()
        for key, data in raw.items():
            (out / f"{key}.json").write_text(json.dumps(data, indent=2))
        typer.echo(f"Collected {len(raw)} datasets to {out}")
    except Exception as exc:
        typer.echo(f"Collection failed: {exc}", err=True)
        raise typer.Exit(1)


@app.command(help="Normalize raw collected data into validated domain models.")
def normalize(
    raw_dir: Annotated[str, typer.Argument(help="Directory containing raw JSON files from collect.")],
    output_dir: Annotated[str | None, typer.Option("--output-dir")] = None,
) -> None:
    import json
    from src.normalization.normalizer import Normalizer
    settings = load_settings()
    out = Path(output_dir or settings.build_dir) / "normalized.json"
    try:
        normalizer = Normalizer()
        raw: dict[str, Any] = {}
        for f in Path(raw_dir).glob("*.json"):
            raw[f.stem] = json.loads(f.read_text())
        normalized = normalizer.normalize(raw)
        out.write_text(normalized.model_dump_json(indent=2))
        typer.echo(f"Normalized data written to {out}")
    except Exception as exc:
        typer.echo(f"Normalization failed: {exc}", err=True)
        raise typer.Exit(1)


@app.command(help="Generate Edition JSON from normalized data.")
@syncify
async def generate(
    normalized_path: Annotated[str, typer.Argument(help="Path to normalized.json.")],
    output_dir: Annotated[str | None, typer.Option("--output-dir")] = None,
    edition_type: Annotated[str | None, typer.Option("--edition-type", help="morning|midday|evening|late|final|special")] = None,
) -> None:
    from src.editorial.engine import EditorialEngine
    settings = load_settings()
    out_dir = Path(output_dir or settings.build_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        engine = EditorialEngine.from_config(edition_type_override=edition_type)
        edition = await engine.generate(Path(normalized_path))
        out = out_dir / "edition.json"
        out.write_text(edition.model_dump_json(indent=2))
        typer.echo(f"Edition JSON written to {out}")
    except Exception as exc:
        typer.echo(f"Generation failed: {exc}", err=True)
        raise typer.Exit(1)


@app.command(help="Validate an Edition JSON file.")
def validate(
    edition_json: Annotated[str, typer.Argument(help="Path to edition.json.")],
    strict: Annotated[bool, typer.Option("--strict", help="Fail on warnings as well as errors.")] = False,
) -> None:
    from src.validation.validator import ContentValidator
    validator = ContentValidator()
    try:
        report = validator.validate_edition_file(Path(edition_json))
        if report.errors:
            for e in report.errors:
                typer.echo(f"ERROR: {e}", err=True)
            raise typer.Exit(1)
        if report.warnings:
            for w in report.warnings:
                typer.echo(f"WARN: {w}")
            if strict:
                raise typer.Exit(1)
        typer.echo(f"Validation passed ({len(report.warnings)} warnings).")
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Validation error: {exc}", err=True)
        raise typer.Exit(1)


@app.command(help="Render an Edition JSON file to static HTML.")
def render(
    edition_json: Annotated[str | None, typer.Argument(help="Path to edition.json. If omitted, uses build/edition.json.")] = None,
    output_dir: Annotated[str | None, typer.Option("--output-dir")] = None,
) -> None:
    from src.rendering.renderer import render_from_file
    settings = load_settings()
    edition_path = Path(edition_json) if edition_json else Path(settings.build_dir) / "edition.json"
    out_dir = Path(output_dir or settings.build_dir)
    try:
        html_path = render_from_file(edition_path, out_dir)
        typer.echo(f"Rendered to {html_path}")
    except Exception as exc:
        typer.echo(f"Render failed: {exc}", err=True)
        raise typer.Exit(1)


@app.command(help="Publish the rendered build directory to the live site.")
def publish(
    build_dir: Annotated[str | None, typer.Argument(help="Build directory to publish. Defaults to build/.")] = None,
    edition_id: Annotated[str | None, typer.Option("--edition-id")] = None,
) -> None:
    from src.publishing.publisher import Publisher
    settings = load_settings()
    src = Path(build_dir or settings.build_dir)
    pub = Publisher(
        publish_root=Path(settings.publish_root),
        archive_root=Path(settings.archive_root),
        last_known_good_path=Path(settings.publish_root) / "index.html.lkg",
        cdn_purge_hook=settings.cdn_purge_hook,
    )
    try:
        pub.publish(src, edition_id or "manual")
        typer.echo("Published successfully.")
    except Exception as exc:
        typer.echo(f"Publish failed: {exc}", err=True)
        raise typer.Exit(1)


@app.command(help="Run the full generation pipeline end to end.")
@syncify
async def run(
    game_date: Annotated[str | None, typer.Option("--date", help="Date in YYYY-MM-DD.")] = None,
    edition_type: Annotated[str | None, typer.Option("--edition-type")] = None,
    edition_json: Annotated[str | None, typer.Option("--edition-json", help="Skip collect/normalize/generate and render from this file.")] = None,
    publish_flag: Annotated[bool, typer.Option("--publish/--no-publish", help="Publish after render.")] = True,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Generate and render but do not publish.")] = False,
    output_dir: Annotated[str | None, typer.Option("--output-dir")] = None,
) -> None:
    from src.pipeline.orchestrator import GenerationOrchestrator
    settings = load_settings()
    target = date.fromisoformat(game_date) if game_date else date.today()
    build = Path(output_dir or settings.build_dir)
    build.mkdir(parents=True, exist_ok=True)

    orchestrator = GenerationOrchestrator(
        build_dir=build,
        publish_root=Path(settings.publish_root),
        archive_root=Path(settings.archive_root),
        game_date=target,
        dry_run=dry_run or not publish_flag,
    )
    edition_override = Path(edition_json) if edition_json else None
    result = await orchestrator.run(edition_json_override=edition_override)

    if result.final_status in ("failed",):
        typer.echo(f"Pipeline failed: {result.error}", err=True)
        raise typer.Exit(1)
    typer.echo(f"Pipeline completed: {result.final_status}")
```

**Alternative considered:** `argparse` or `click`. Rejected — Typer provides type inference from Python annotations, automatic `--help` generation, and better IDE support with no significant overhead.

---

## Data Storage

The pipeline does not use a relational database. All persistence is filesystem-based.

### Directory layout

```text
build/
├── <edition-id>/                   # one directory per pipeline run
│   ├── raw/
│   │   ├── schedule.json           # raw MLB Stats API response
│   │   ├── standings.json
│   │   ├── transactions.json
│   │   └── injuries.json
│   ├── normalized.json             # serialized NormalizedData model
│   ├── edition.json                # the Edition document
│   ├── validation-report.json      # ValidationReport model
│   ├── index.html                  # rendered HTML
│   └── run.json                    # GenerationRun observability record
/daily-sports-page/
├── index.html                      # live published page
├── index.html.lkg                  # last-known-good for rollback
├── archive/
│   ├── 2026-07-13-0600.html
│   └── 2026-07-13-1200.html
└── static/
    ├── css/main.<hash>.css
    └── js/main.<hash>.js
```

### Cache file naming

Raw provider responses are cached in `build/<edition-id>/raw/` keyed by provider and data type. Freshness is checked before re-use by comparing the file mtime against the configurable max-age for that data type.

```python
# src/storage/cache.py
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
```

### Run log model

```python
# src/models/run.py
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    started = "started"
    collecting = "collecting"
    normalizing = "normalizing"
    generating = "generating"
    validating = "validating"
    rendering = "rendering"
    publishing = "publishing"
    published = "published"
    failed = "failed"
    published_degraded = "published_degraded"


class PhaseStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class RunPhase(BaseModel):
    name: str = Field(description="Phase name matching RunStatus values.")
    status: PhaseStatus
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    note: str | None = Field(default=None, description="Optional note, e.g. skip reason or error summary.")

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class ProviderStatus(BaseModel):
    provider: str
    available: bool
    response_time_ms: float | None = Field(default=None)
    error: str | None = Field(default=None)
    used_cache: bool = False


class GenerationRun(BaseModel):
    """Observability record for a single pipeline execution."""
    run_id: str = Field(default_factory=lambda: str(uuid4()), description="Unique run identifier.")
    edition_id: str | None = Field(default=None)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = Field(default=None)
    phases: list[RunPhase] = Field(default_factory=list)
    provider_statuses: list[ProviderStatus] = Field(default_factory=list)
    final_status: RunStatus = Field(default=RunStatus.started)
    error: str | None = Field(default=None)
    ai_used: bool = False
    ai_fallback_count: int = Field(default=0, description="Number of sections that fell back to deterministic templates.")

    @classmethod
    def start(cls) -> "GenerationRun":
        return cls()

    def record_phase(self, name: str, status: PhaseStatus, note: str | None = None) -> None:
        now = datetime.now(timezone.utc)
        for phase in self.phases:
            if phase.name == name:
                phase.status = status
                if status == PhaseStatus.in_progress:
                    phase.started_at = now
                elif status in (PhaseStatus.completed, PhaseStatus.failed, PhaseStatus.skipped):
                    phase.completed_at = now
                if note:
                    phase.note = note
                return
        self.phases.append(RunPhase(
            name=name,
            status=status,
            started_at=now if status == PhaseStatus.in_progress else None,
            completed_at=now if status != PhaseStatus.in_progress else None,
            note=note,
        ))

    def complete(self, status: RunStatus, error: str | None = None) -> None:
        self.final_status = status
        self.completed_at = datetime.now(timezone.utc)
        if error:
            self.error = error
```

---

## Data Structures

All models below are Pydantic v2. Models representing pipeline inputs and outputs are kept separate.

```python
# src/models/standings.py
from pydantic import BaseModel, Field


class StandingsRow(BaseModel):
    """A single team row in a division standings table."""
    team_id: int = Field(description="MLB team ID.")
    team_abbr: str = Field(description="Team abbreviation, e.g. NYY.")
    team_name: str = Field(description="Full team name.")
    wins: int = Field(description="Season wins.")
    losses: int = Field(description="Season losses.")
    pct: float = Field(description="Winning percentage.")
    games_back: float | str = Field(description="Games behind division leader. 0.0 for the leader, '-' for tied leader.")
    last_10: str = Field(description="Record over last 10 games, e.g. 6-4.")
    streak: str = Field(description="Current streak, e.g. W3 or L1.")
    home_record: str = Field(description="Home record, e.g. 30-20.")
    away_record: str = Field(description="Away record, e.g. 28-22.")
    run_differential: int = Field(description="Runs scored minus runs allowed.")
    wild_card_gb: float | str | None = Field(default=None, description="Wild card games behind. None for AL/NL division leaders already in standings.")
    eliminated: bool = Field(default=False)
    magic_number: int | None = Field(default=None, description="Magic number to clinch. None if eliminated or not yet applicable.")


class DivisionStandings(BaseModel):
    division_id: int
    division_name: str = Field(description="e.g. AL East.")
    rows: list[StandingsRow] = Field(min_length=1)


class WildCardStandings(BaseModel):
    league: str = Field(description="AL or NL.")
    rows: list[StandingsRow] = Field(min_length=1)


class Standings(BaseModel):
    divisions: list[DivisionStandings] = Field(description="All 6 MLB divisions.")
    wild_cards: list[WildCardStandings] = Field(description="AL and NL wild card standings.")
```

```python
# src/models/leaders.py
from pydantic import BaseModel, Field


class LeaderEntry(BaseModel):
    """A single player entry in a league-leaders leaderboard."""
    rank: int = Field(ge=1, description="Rank within this category (1 = best).")
    player_id: int = Field(description="MLB player ID.")
    player_name: str
    team_abbr: str
    position: str = Field(description="Primary position abbreviation, e.g. SP, CF, 1B.")
    value: str = Field(description="Formatted stat value, e.g. .342 or 2.81 or 23.")
    games_played: int
    league: str = Field(description="AL or NL.")
    qualified: bool = Field(description="Whether the player meets qualification thresholds.")


class LeagueLeaders(BaseModel):
    """All leader boards for a given edition."""
    batting: dict[str, list[LeaderEntry]] = Field(
        description="Keyed by batting category (avg, obp, slg, ops, hr, rbi, r, h, doubles, triples, sb, bb, so).",
    )
    pitching: dict[str, list[LeaderEntry]] = Field(
        description="Keyed by pitching category (era, whip, wins, k, k9, bb9, hr9, saves, holds, ip, qs, cg, sho, sv_pct, fip).",
    )
```

```python
# src/models/story.py
from __future__ import annotations
from enum import Enum
from pydantic import BaseModel, Field
from src.models.game import Pitcher


class StoryType(str, Enum):
    lead = "lead"
    secondary = "secondary"
    game_recap = "game_recap"
    division_snapshot = "division_snapshot"
    wild_card_watch = "wild_card_watch"
    rookie_watch = "rookie_watch"
    editorial = "editorial"
    transaction_summary = "transaction_summary"


class Story(BaseModel):
    """An AI-generated or deterministic editorial story."""
    headline: str = Field(description="Story headline. Must not be invented — grounded in structured data.")
    deck: str = Field(description="Subheadline / summary sentence.")
    byline: str = Field(default="SportzBallz Staff")
    paragraphs: list[str] = Field(min_length=1, description="Body paragraphs.")
    source_data_references: list[str] = Field(
        default_factory=list,
        description="Keys from Edition JSON that ground this story, e.g. game:748293.",
    )
    story_type: StoryType
    teams: list[str] = Field(default_factory=list, description="Team abbreviations mentioned.")
    players: list[str] = Field(default_factory=list, description="Player names mentioned.")
    facts_used: list[str] = Field(
        default_factory=list,
        description="Enumeration of facts from structured data used in this story.",
    )
    ai_generated: bool = Field(default=True)


class GameRecap(Story):
    """A game recap story. Extends Story with game-specific fields."""
    game_id: int = Field(description="MLB game PK this recap covers.")
    final_score: str = Field(description="Formatted final score, e.g. NYY 5, BOS 3.")
    winning_pitcher: Pitcher | None = Field(default=None)
    losing_pitcher: Pitcher | None = Field(default=None)
    save_pitcher: Pitcher | None = Field(default=None)
    tags: list[str] = Field(
        default_factory=list,
        description="walk-off, extra-inning, no-hitter, perfect-game, shutout, doubleheader, etc.",
    )
```

```python
# src/models/transactions.py
from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    trade = "trade"
    dfa = "dfa"
    released = "released"
    signed = "signed"
    optioned = "optioned"
    recalled = "recalled"
    placed_on_il = "placed_on_il"
    activated = "activated"
    claimed = "claimed"
    retired = "retired"
    other = "other"


class Transaction(BaseModel):
    """A single roster transaction."""
    transaction_id: str = Field(description="Provider-assigned transaction ID for deduplication.")
    team_abbr: str
    team_name: str
    player_name: str
    player_id: int | None = Field(default=None)
    transaction_type: TransactionType
    effective_date: date
    explanation: str = Field(description="Human-readable description of the transaction.")
    source_timestamp: datetime = Field(description="When the provider reported this transaction.")
```

```python
# src/models/injuries.py
from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from pydantic import BaseModel, Field


class RosterStatus(str, Enum):
    ten_day_il = "10-day-il"
    fifteen_day_il = "15-day-il"
    sixty_day_il = "60-day-il"
    day_to_day = "day-to-day"
    out = "out"


class InjuryConfidence(str, Enum):
    confirmed = "confirmed"       # official team/MLB statement
    reported = "reported"         # credible media report
    speculative = "speculative"   # unverified


class Injury(BaseModel):
    """An injury report entry. The system MUST NOT invent return dates."""
    player_id: int
    player_name: str
    team_abbr: str
    injury_description: str = Field(description="Nature of the injury, e.g. right hamstring strain.")
    roster_status: RosterStatus
    date_of_injury: date | None = Field(default=None)
    expected_return: str | None = Field(
        default=None,
        description=(
            "Expected return timeline as a string, e.g. 'mid-August' or 'day-to-day'. "
            "NEVER generated — only populated from verified provider data."
        ),
    )
    confidence_level: InjuryConfidence
    latest_update: str | None = Field(default=None, description="Most recent status update text.")
    update_timestamp: datetime | None = Field(default=None)
```

```python
# src/models/history.py
from pydantic import BaseModel, Field


class HistoricalItem(BaseModel):
    """A 'this day in baseball history' item."""
    year: int = Field(ge=1839)
    headline: str = Field(description="Brief summary of the historical event.")
    description: str = Field(description="One to two sentence description.")
    teams: list[str] = Field(default_factory=list)
    players: list[str] = Field(default_factory=list)
    source: str = Field(description="Data source attribution for this historical fact.")
    verified: bool = Field(default=True, description="False if sourced from unverified community data.")
```

```python
# src/models/freshness.py
from datetime import datetime
from pydantic import BaseModel, Field


class DataFreshness(BaseModel):
    """Per-section data freshness timestamps for display and staleness warnings."""
    live_scores_as_of: datetime | None = Field(default=None)
    standings_as_of: datetime | None = Field(default=None)
    schedule_as_of: datetime | None = Field(default=None)
    league_leaders_as_of: datetime | None = Field(default=None)
    transactions_as_of: datetime | None = Field(default=None)
    injuries_as_of: datetime | None = Field(default=None)
    historical_as_of: datetime | None = Field(default=None)
    max_age_warnings: list[str] = Field(
        default_factory=list,
        description="Human-readable warnings for sections exceeding freshness thresholds.",
    )
```

```python
# src/models/edition.py  (complete Edition root document)
from __future__ import annotations
from pydantic import BaseModel, Field
from src.models.game import Game
from src.models.standings import Standings
from src.models.leaders import LeagueLeaders
from src.models.story import Story, GameRecap
from src.models.transactions import Transaction
from src.models.injuries import Injury
from src.models.history import HistoricalItem
from src.models.freshness import DataFreshness
from src.models.run import GenerationRun


class GenerationMetadata(BaseModel):
    pipeline_version: str = Field(description="semver of the daily-sports-page package.")
    python_version: str
    ai_provider: str | None = Field(default=None, description="AI provider used for story generation.")
    ai_model: str | None = Field(default=None)
    ai_fallbacks: int = Field(default=0, description="Number of sections using deterministic fallback.")
    total_duration_seconds: float | None = Field(default=None)
    data_freshness: DataFreshness = Field(default_factory=DataFreshness)


class Edition(BaseModel):
    """Root Edition JSON document. All HTML rendering is a pure function of this model."""
    edition: EditionMetadata
    lead_story: Story | None = Field(default=None)
    secondary_stories: list[Story] = Field(default_factory=list, description="3–6 secondary front-page stories.")
    games: list[Game] = Field(default_factory=list)
    standings: Standings | None = Field(default=None)
    league_leaders: LeagueLeaders | None = Field(default=None)
    game_recaps: list[GameRecap] = Field(default_factory=list)
    around_the_league: list[Story] = Field(default_factory=list, description="Division snapshots, wild-card watch, etc.")
    transactions: list[Transaction] = Field(default_factory=list)
    injuries: list[Injury] = Field(default_factory=list)
    historical_items: list[HistoricalItem] = Field(default_factory=list)
    generation_metadata: GenerationMetadata = Field(default_factory=GenerationMetadata)
```

---

## Interfaces

### CLI Commands

| Command                        | Arguments / Options                                                                                                                        | Description                                                   | Exit codes    |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------- | ------------- |
| `daily-sports-page collect`    | `--date YYYY-MM-DD` (opt), `--output-dir PATH` (opt)                                                                                       | Fetch raw data from all providers                             | 0 success, 1 error |
| `daily-sports-page normalize`  | `RAW_DIR` (positional), `--output-dir PATH` (opt)                                                                                          | Normalize raw JSON to domain models                           | 0 success, 1 error |
| `daily-sports-page generate`   | `NORMALIZED_PATH` (positional), `--output-dir PATH` (opt), `--edition-type TYPE` (opt)                                                     | Run editorial engine and AI generation; write edition.json    | 0 success, 1 error |
| `daily-sports-page validate`   | `EDITION_JSON` (positional), `--strict` (flag)                                                                                              | Validate edition.json against schema and content rules        | 0 pass, 1 error/strict-warn |
| `daily-sports-page render`     | `EDITION_JSON` (positional, opt — defaults to `build/edition.json`), `--output-dir PATH` (opt)                                             | Render edition.json to index.html                             | 0 success, 1 error |
| `daily-sports-page publish`    | `BUILD_DIR` (positional, opt — defaults to `build/`), `--edition-id ID` (opt)                                                              | Atomically publish rendered HTML to live site                 | 0 success, 1 error |
| `daily-sports-page run`        | `--date YYYY-MM-DD` (opt), `--edition-type TYPE` (opt), `--edition-json PATH` (opt), `--publish/--no-publish`, `--dry-run`, `--output-dir` | Full pipeline. See below.                                     | 0 success, 1 error |

### `run` command full flag set

| Flag                       | Default    | Description                                                                                    |
| -------------------------- | ---------- | ---------------------------------------------------------------------------------------------- |
| `--date YYYY-MM-DD`        | today      | Target game date for collection and edition generation.                                        |
| `--edition-type TYPE`      | auto       | Force a specific edition type instead of deriving from time-of-day.                            |
| `--edition-json PATH`      | none       | Skip collect/normalize/generate; render directly from this Edition JSON file.                  |
| `--publish / --no-publish` | `--publish` | Whether to run the publish step after render.                                                  |
| `--dry-run`                | false      | Generate and render but do not publish. Implies `--no-publish`. Writes output to `--output-dir`. |
| `--output-dir PATH`        | `build/`   | Override the build output directory.                                                           |

When `--edition-json` is provided, the pipeline jumps directly to the validate and render stages. This is the primary mechanism for template development and for re-rendering historical editions without API calls.

### Config file formats

```yaml
# config/settings.yaml
build_dir: build
publish_root: /var/www/sportzballz/daily-sports-page
archive_root: /var/www/sportzballz/daily-sports-page/archive
cdn_purge_hook: null        # path to shell script or null

mlb_api:
  base_url: https://statsapi.mlb.com/api/v1
  timeout_seconds: 10
  max_attempts: 3
  backoff_min_seconds: 1.0
  backoff_max_seconds: 30.0

ai:
  provider: openai           # openai | anthropic | none
  model: gpt-4o
  timeout_seconds: 30
  max_retries: 2

freshness_max_age_seconds:
  live_scores: 300           # 5 min
  scheduled_games: 1800      # 30 min
  standings: 1800
  league_leaders: 21600      # 6 hr
  transactions: 1800
  injuries: 7200             # 2 hr
  historical_data: 2592000   # 30 days

performance:
  html_max_bytes: 512000
  total_page_max_bytes: 2097152
```

```yaml
# config/editorial.yaml
scoring_weights:
  playoff_weight: 3.0
  historic_weight: 2.5
  performance_weight: 2.0
  game_drama_weight: 1.5
  national_interest_weight: 1.0
  recency_weight: 0.5

secondary_story_count:
  min: 3
  max: 6

manual_lead_overrides: {}
  # game_id: score

large_market_teams:
  - NYY
  - NYM
  - LAD
  - CHC
  - BOS
  - SF
  - PHI
  - ATL
  - HOU
  - STL
```

```yaml
# config/schedules.yaml
timezone: America/New_York

editions:
  - type: morning
    cron: "0 6 * * *"
    description: Previous-day results emphasis. Full recaps.
  - type: midday
    cron: "0 12 * * *"
    description: Updated standings and transactions. Preview afternoon games.
  - type: evening
    cron: "0 18 * * *"
    description: Night-game previews emphasis.
  - type: late
    cron: "0 22 * * *"
    description: Early game finals. In-progress updates for night games.
  - type: final
    cron: "30 1 * * *"
    description: Full final results for all completed games.
```

## Accessibility

### Semantic structure

All eight page sections use native HTML landmark elements (`<main>`, `<section>`, `<article>`, `<nav>`, `<header>`, `<footer>`). Each section has a stable `id` attribute (`#front-page`, `#scoreboard`, `#todays-games`, `#standings`, `#league-leaders`, `#game-recaps`, `#around-the-league`, `#transactions`, `#injuries`, `#history`) that functions as a skip link target. A skip navigation link (`<a href="#front-page" class="skip-link">Skip to content</a>`) is the first focusable element in the document.

### Color and contrast

All text meets WCAG 2.1 AA minimum contrast ratios: 4.5:1 for normal text, 3:1 for large text and UI components. No information is conveyed by color alone. Game status indicators (final, in progress, postponed) include text labels alongside any color coding.

### Keyboard navigation

The league-leaders tab switcher is the only JavaScript-dependent interactive component. It implements `role="tablist"`, `role="tab"`, and `role="tabpanel"` with arrow-key navigation, `tabindex` management, and `aria-selected` state. Tab focus falls back gracefully to displaying all categories stacked when JavaScript is absent, preserving full content access.

### Screen readers

Dynamic freshness warnings rendered by JavaScript use `aria-live="polite"` regions. The scoreboard in-progress indicator updates (if any) are announced via a live region. All data tables include `<caption>` elements and `<th scope="col">` headers.

### Motion

No animations are present in the baseline design. If transition effects are added to the tab switcher or any other component, they must respect `prefers-reduced-motion` via a CSS media query that removes or reduces the animation.

---

## Implementation Detail

### Normalizer

```python
# src/normalization/normalizer.py
from __future__ import annotations
import logging
from datetime import date
from typing import Any
from pydantic import BaseModel, Field
from src.models.game import Game, GameStatus, TeamGameLine, Pitcher, LinescoreInning
from src.models.standings import StandingsRow, DivisionStandings, WildCardStandings, Standings
from src.models.transactions import Transaction, TransactionType
from src.models.injuries import Injury, RosterStatus, InjuryConfidence

logger = logging.getLogger(__name__)


class NormalizedData(BaseModel):
    """All provider data normalized to domain models, ready for editorial processing."""
    games: list[Game] = Field(default_factory=list)
    standings: Standings | None = Field(default=None)
    transactions: list[Transaction] = Field(default_factory=list)
    injuries: list[Injury] = Field(default_factory=list)
    collection_errors: list[str] = Field(default_factory=list, description="Non-fatal collection errors logged here.")


class Normalizer:
    """Converts raw MLB Stats API responses to validated Pydantic domain models."""

    _GAME_STATUS_MAP: dict[str, GameStatus] = {
        "Final": GameStatus.final,
        "Game Over": GameStatus.final,
        "In Progress": GameStatus.in_progress,
        "Scheduled": GameStatus.scheduled,
        "Pre-Game": GameStatus.scheduled,
        "Warmup": GameStatus.scheduled,
        "Postponed": GameStatus.postponed,
        "Delayed": GameStatus.delayed,
        "Delayed: Rain": GameStatus.delayed,
        "Suspended": GameStatus.suspended,
    }

    _TRANSACTION_TYPE_MAP: dict[str, TransactionType] = {
        "Trade": TransactionType.trade,
        "Designated for Assignment": TransactionType.dfa,
        "Released": TransactionType.released,
        "Signed": TransactionType.signed,
        "Optioned to Minors": TransactionType.optioned,
        "Recalled from Minors": TransactionType.recalled,
        "Placed on 10-Day IL": TransactionType.placed_on_il,
        "Placed on 15-Day IL": TransactionType.placed_on_il,
        "Placed on 60-Day IL": TransactionType.placed_on_il,
        "Activated from IL": TransactionType.activated,
        "Claimed off Waivers": TransactionType.claimed,
        "Retired": TransactionType.retired,
    }

    def normalize(self, raw: dict[str, Any]) -> NormalizedData:
        """Normalize a full raw provider response dict."""
        result = NormalizedData()
        if "schedule" in raw:
            result.games = self._normalize_schedule(raw["schedule"])
        if "standings" in raw:
            result.standings = self._normalize_standings(raw["standings"])
        if "transactions" in raw:
            result.transactions = self._normalize_transactions(raw["transactions"])
        if "injuries" in raw:
            result.injuries = self._normalize_injuries(raw["injuries"])
        return result

    def _normalize_schedule(self, raw: dict[str, Any]) -> list[Game]:
        games: list[Game] = []
        for date_entry in raw.get("dates", []):
            for g in date_entry.get("games", []):
                try:
                    games.append(self._parse_game(g))
                except Exception as exc:
                    logger.warning("failed to parse game %s: %s", g.get("gamePk"), exc)
        return games

    def _parse_game(self, g: dict[str, Any]) -> Game:
        status_detail = g.get("status", {}).get("detailedState", "Scheduled")
        status = self._GAME_STATUS_MAP.get(status_detail, GameStatus.scheduled)
        teams = g.get("teams", {})
        linescore = g.get("linescore", {})
        innings_raw = linescore.get("innings", [])
        innings = [
            LinescoreInning(
                inning=inn.get("num", i + 1),
                away_runs=inn.get("away", {}).get("runs"),
                home_runs=inn.get("home", {}).get("runs"),
            )
            for i, inn in enumerate(innings_raw)
        ]
        decisions = g.get("decisions", {})
        broadcasts = [b.get("name", "") for b in g.get("broadcasts", []) if b.get("name")]

        return Game(
            game_id=g["gamePk"],
            game_date=g.get("gameDate", "")[:10],
            game_time_et=self._format_time(g.get("gameDate", "")),
            status=status,
            inning=linescore.get("currentInning"),
            inning_state=linescore.get("inningState"),
            home=self._parse_team_line(teams.get("home", {}), linescore.get("teams", {}).get("home", {})),
            away=self._parse_team_line(teams.get("away", {}), linescore.get("teams", {}).get("away", {})),
            linescore=innings,
            home_probable_pitcher=self._parse_pitcher(teams.get("home", {}).get("probablePitcher")),
            away_probable_pitcher=self._parse_pitcher(teams.get("away", {}).get("probablePitcher")),
            winning_pitcher=self._parse_pitcher(decisions.get("winner")),
            losing_pitcher=self._parse_pitcher(decisions.get("loser")),
            save_pitcher=self._parse_pitcher(decisions.get("save")),
            venue_name=g.get("venue", {}).get("name"),
            venue_city=g.get("venue", {}).get("location", {}).get("city"),
            tv_broadcasts=broadcasts,
            weather_description=g.get("weather", {}).get("condition"),
            is_doubleheader=g.get("doubleHeader") != "N",
            doubleheader_game_num=g.get("gameNumber"),
        )

    def _parse_team_line(self, team: dict, line: dict) -> TeamGameLine:
        return TeamGameLine(
            team_id=team.get("team", {}).get("id", 0),
            team_abbr=team.get("team", {}).get("abbreviation", "UNK"),
            team_name=team.get("team", {}).get("name", "Unknown"),
            runs=line.get("runs"),
            hits=line.get("hits"),
            errors=line.get("errors"),
        )

    def _parse_pitcher(self, data: dict | None) -> Pitcher | None:
        if not data:
            return None
        stats = data.get("stats", [{}])[0].get("stats", {}) if data.get("stats") else {}
        return Pitcher(
            player_id=data.get("id", 0),
            name=data.get("fullName", data.get("name", "")),
            handedness=data.get("pitchHand", {}).get("code") if data.get("pitchHand") else None,
            wins=stats.get("wins"),
            losses=stats.get("losses"),
            era=stats.get("era"),
        )

    def _format_time(self, iso: str) -> str | None:
        if not iso:
            return None
        try:
            from datetime import datetime
            import pytz
            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            et = dt.astimezone(pytz.timezone("America/New_York"))
            return et.strftime("%-I:%M %p ET")
        except Exception:
            return None

    def _normalize_standings(self, raw: dict[str, Any]) -> Standings:
        divisions: list[DivisionStandings] = []
        wild_cards: list[WildCardStandings] = []
        seen_division_ids: set[int] = set()

        for record in raw.get("records", []):
            div = record.get("division", {})
            div_id = div.get("id", 0)
            div_name = div.get("nameShort", div.get("name", ""))
            rows = [self._parse_standings_row(tr) for tr in record.get("teamRecords", [])]
            if div_id not in seen_division_ids:
                divisions.append(DivisionStandings(division_id=div_id, division_name=div_name, rows=rows))
                seen_division_ids.add(div_id)

        return Standings(divisions=divisions, wild_cards=wild_cards)

    def _parse_standings_row(self, tr: dict[str, Any]) -> StandingsRow:
        team = tr.get("team", {})
        split_records = {r.get("type"): r for r in tr.get("records", {}).get("splitRecords", [])}
        home = split_records.get("home", {})
        away = split_records.get("away", {})
        last_10 = split_records.get("lastTen", {})
        streak = tr.get("streak", {}).get("streakCode", "")
        return StandingsRow(
            team_id=team.get("id", 0),
            team_abbr=team.get("abbreviation", ""),
            team_name=team.get("name", ""),
            wins=tr.get("wins", 0),
            losses=tr.get("losses", 0),
            pct=float(tr.get("winningPercentage", "0.000")),
            games_back=tr.get("gamesBack", "-"),
            last_10=f"{last_10.get('wins', 0)}-{last_10.get('losses', 0)}",
            streak=streak,
            home_record=f"{home.get('wins', 0)}-{home.get('losses', 0)}",
            away_record=f"{away.get('wins', 0)}-{away.get('losses', 0)}",
            run_differential=tr.get("runDifferential", 0),
        )

    def _normalize_transactions(self, raw: dict[str, Any]) -> list[Transaction]:
        seen: set[str] = set()
        result: list[Transaction] = []
        for t in raw.get("transactions", []):
            tid = str(t.get("id", ""))
            if tid in seen:
                continue
            seen.add(tid)
            try:
                result.append(Transaction(
                    transaction_id=tid,
                    team_abbr=t.get("fromTeam", {}).get("abbreviation", t.get("toTeam", {}).get("abbreviation", "")),
                    team_name=t.get("fromTeam", {}).get("name", t.get("toTeam", {}).get("name", "")),
                    player_name=t.get("person", {}).get("fullName", ""),
                    player_id=t.get("person", {}).get("id"),
                    transaction_type=self._TRANSACTION_TYPE_MAP.get(
                        t.get("typeDesc", ""), TransactionType.other
                    ),
                    effective_date=date.fromisoformat(t["date"][:10]),
                    explanation=t.get("description", t.get("typeDesc", "")),
                    source_timestamp=t.get("date", ""),
                ))
            except Exception as exc:
                logger.warning("skipping transaction %s: %s", tid, exc)
        return result

    def _normalize_injuries(self, raw: dict[str, Any]) -> list[Injury]:
        result: list[Injury] = []
        for item in raw.get("injuries", []):
            try:
                result.append(Injury(
                    player_id=item.get("player", {}).get("id", 0),
                    player_name=item.get("player", {}).get("fullName", ""),
                    team_abbr=item.get("team", {}).get("abbreviation", ""),
                    injury_description=item.get("notes", ""),
                    roster_status=RosterStatus.ten_day_il,
                    confidence_level=InjuryConfidence.reported,
                ))
            except Exception as exc:
                logger.warning("skipping injury: %s", exc)
        return result
```

### StatisticsProcessor

```python
# src/statistics/processor.py
from __future__ import annotations
import logging
from src.models.game import Game, GameStatus
from src.models.standings import StandingsRow
from src.normalization.normalizer import NormalizedData

logger = logging.getLogger(__name__)


class NotablePerformance:
    """Detected notable performances for editorial scoring."""
    def __init__(self, game_id: int, tags: list[str], performance_score: float) -> None:
        self.game_id = game_id
        self.tags = tags
        self.performance_score = performance_score


class StatisticsProcessor:
    """Computes derived statistics and detects notable performances."""

    def detect_notable_performances(self, games: list[Game]) -> dict[int, NotablePerformance]:
        """Detect walk-offs, extra innings, no-hitters, and score differential."""
        result: dict[int, NotablePerformance] = {}
        for game in games:
            if game.status != GameStatus.final:
                continue
            tags: list[str] = []
            score = 0.0

            home_runs = game.home.runs or 0
            away_runs = game.away.runs or 0
            total_innings = len(game.linescore)

            if total_innings > 9:
                tags.append("extra-inning")
                score += 0.5

            if total_innings >= 9:
                last = game.linescore[-1]
                home_is_winner = home_runs > away_runs
                if home_is_winner and last.home_runs and last.home_runs > 0:
                    tags.append("walk-off")
                    score += 0.8

            diff = abs(home_runs - away_runs)
            if diff == 0:
                score += 0.3
            elif diff <= 1:
                score += 0.2

            score += min((home_runs + away_runs) / 20.0, 0.5)

            result[game.game_id] = NotablePerformance(game.game_id, tags, min(score, 1.0))
        return result

    def sort_games_by_editorial_significance(
        self,
        games: list[Game],
        performances: dict[int, NotablePerformance],
    ) -> list[Game]:
        """Sort final games by editorial significance for recap ordering."""
        def key(g: Game) -> float:
            if g.status != GameStatus.final:
                return -1.0
            perf = performances.get(g.game_id)
            return perf.performance_score if perf else 0.0

        return sorted(games, key=key, reverse=True)
```

### EditorialEngine

```python
# src/editorial/engine.py
from __future__ import annotations
import json
import logging
from pathlib import Path
from src.models.edition import Edition, EditionMetadata, GenerationMetadata, EditionType
from src.models.story import Story, GameRecap, StoryType
from src.models.game import GameStatus
from src.normalization.normalizer import NormalizedData
from src.editorial.scoring import ScoringWeights, ScoringContext, score_game
from src.editorial.fallback import generate_fallback_recap
from src.statistics.processor import StatisticsProcessor
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class EditorialEngine:
    """Orchestrates editorial selection, story generation, and Edition JSON assembly."""

    def __init__(
        self,
        scoring_weights: ScoringWeights,
        manual_overrides: dict[int, float],
        large_market_teams: set[str],
        edition_type_override: str | None = None,
        ai_client: object | None = None,
    ) -> None:
        self._weights = scoring_weights
        self._overrides = manual_overrides
        self._large_market = large_market_teams
        self._edition_type_override = edition_type_override
        self._ai_client = ai_client
        self._stats = StatisticsProcessor()

    @classmethod
    def from_config(cls, edition_type_override: str | None = None) -> "EditorialEngine":
        import yaml
        cfg = yaml.safe_load(Path("config/editorial.yaml").read_text())
        weights = ScoringWeights(**cfg.get("scoring_weights", {}))
        overrides = {int(k): float(v) for k, v in cfg.get("manual_lead_overrides", {}).items()}
        large_market = set(cfg.get("large_market_teams", []))
        return cls(
            scoring_weights=weights,
            manual_overrides=overrides,
            large_market_teams=large_market,
            edition_type_override=edition_type_override,
        )

    async def generate(self, normalized_path: Path) -> Edition:
        """Generate an Edition from a normalized data file."""
        raw = json.loads(normalized_path.read_text())
        normalized = NormalizedData.model_validate(raw)

        edition_type = self._derive_edition_type()
        edition_id = self._make_edition_id(edition_type)
        performances = self._stats.detect_notable_performances(normalized.games)

        for game_id, perf in performances.items():
            for game in normalized.games:
                if game.game_id == game_id:
                    game.tags = list(set(game.tags + perf.tags))

        scored_games = [
            (
                g,
                score_game(
                    g,
                    ScoringContext(
                        has_historic_performance=bool(set(g.tags) & {"no-hitter", "perfect-game"}),
                        performance_score=performances.get(g.game_id, object).__class__.__dict__.get("performance_score", 0.0)
                        if g.game_id in performances else 0.0,
                        drama_score=performances[g.game_id].performance_score if g.game_id in performances else 0.0,
                        is_nationally_televised=any(n in ("ESPN", "FOX", "FS1", "TBS", "MLB Network") for n in g.tv_broadcasts),
                        is_large_market=g.home.team_abbr in self._large_market or g.away.team_abbr in self._large_market,
                    ),
                    self._weights,
                    self._overrides,
                ),
            )
            for g in normalized.games
            if g.status == GameStatus.final
        ]
        scored_games.sort(key=lambda x: x[1], reverse=True)

        lead_story: Story | None = None
        secondary_stories: list[Story] = []
        game_recaps: list[GameRecap] = []
        ai_fallbacks = 0

        for i, (game, score) in enumerate(scored_games):
            recap = await self._generate_recap(game)
            if recap.ai_generated is False:
                ai_fallbacks += 1
            game_recaps.append(recap)
            if i == 0:
                lead_story = Story(
                    headline=recap.headline,
                    deck=recap.deck,
                    byline=recap.byline,
                    paragraphs=recap.paragraphs,
                    source_data_references=recap.source_data_references,
                    story_type=StoryType.lead,
                    teams=recap.teams,
                    players=recap.players,
                    facts_used=recap.facts_used,
                    ai_generated=recap.ai_generated,
                )
            elif i < 6:
                secondary_stories.append(Story(
                    headline=recap.headline,
                    deck=recap.deck,
                    byline=recap.byline,
                    paragraphs=recap.paragraphs[:1],
                    source_data_references=recap.source_data_references,
                    story_type=StoryType.secondary,
                    teams=recap.teams,
                    players=recap.players,
                    facts_used=recap.facts_used,
                    ai_generated=recap.ai_generated,
                ))

        return Edition(
            edition=EditionMetadata(
                id=edition_id,
                type=edition_type,
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                generated_at=datetime.now(timezone.utc),
                data_current_through=datetime.now(timezone.utc),
                status="draft",
            ),
            lead_story=lead_story,
            secondary_stories=secondary_stories,
            games=normalized.games,
            standings=normalized.standings,
            game_recaps=game_recaps,
            transactions=normalized.transactions,
            injuries=normalized.injuries,
            generation_metadata=GenerationMetadata(
                pipeline_version="0.1.0",
                python_version=__import__("platform").python_version(),
                ai_fallbacks=ai_fallbacks,
            ),
        )

    async def _generate_recap(self, game) -> GameRecap:
        """Generate a recap via AI, falling back to deterministic template."""
        if self._ai_client is None:
            return generate_fallback_recap(game)
        try:
            return await self._generate_ai_recap(game)
        except Exception as exc:
            logger.warning("AI recap failed for game %d, using fallback: %s", game.game_id, exc)
            return generate_fallback_recap(game)

    async def _generate_ai_recap(self, game) -> GameRecap:
        """Build the AI prompt and call the provider."""
        raise NotImplementedError("AI recap generation to be implemented with provider SDK.")

    def _derive_edition_type(self) -> EditionType:
        if self._edition_type_override:
            return self._edition_type_override  # type: ignore[return-value]
        hour = datetime.now(timezone.utc).hour
        if hour < 10:
            return "morning"
        if hour < 14:
            return "midday"
        if hour < 20:
            return "evening"
        if hour < 23:
            return "late"
        return "final"

    def _make_edition_id(self, edition_type: EditionType) -> str:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return f"{now.strftime('%Y-%m-%d-%H%M')}"
```

### ContentValidator

```python
# src/validation/validator.py
from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from src.models.edition import Edition

logger = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def summary(self) -> str:
        return f"{len(self.errors)} errors, {len(self.warnings)} warnings"


class ContentValidator:
    """Validates Edition JSON for schema correctness and content integrity."""

    def validate_edition_file(self, path: Path) -> ValidationReport:
        report = ValidationReport()
        try:
            raw = json.loads(path.read_text())
        except Exception as exc:
            report.errors.append(f"Cannot parse JSON: {exc}")
            return report
        try:
            edition = Edition.model_validate(raw)
        except Exception as exc:
            report.errors.append(f"Schema validation failed: {exc}")
            return report
        self._validate_content_rules(edition, report)
        return report

    def _validate_content_rules(self, edition: Edition, report: ValidationReport) -> None:
        """Apply content integrity rules beyond schema validation."""
        for recap in edition.game_recaps:
            self._check_recap_facts(recap, edition, report)
        for injury in edition.injuries:
            if injury.expected_return and injury.confidence_level.value == "speculative":
                report.warnings.append(
                    f"Injury for {injury.player_name}: speculative expected_return '{injury.expected_return}' — verify before publishing."
                )
        for story in [edition.lead_story] + edition.secondary_stories + edition.game_recaps:
            if story is None:
                continue
            text = " ".join(story.paragraphs).lower()
            forbidden = ["according to sources", "reportedly considering", "is expected to sign"]
            for phrase in forbidden:
                if phrase in text:
                    report.errors.append(
                        f"Story '{story.headline}' contains potentially invented phrase: '{phrase}'"
                    )

    def _check_recap_facts(self, recap, edition, report: ValidationReport) -> None:
        game = next((g for g in edition.games if g.game_id == recap.game_id), None)
        if game is None:
            report.errors.append(f"GameRecap references game_id {recap.game_id} not present in edition.games")
            return
        home_runs = game.home.runs or 0
        away_runs = game.away.runs or 0
        expected_score = f"{game.home.team_abbr} {home_runs}, {game.away.team_abbr} {away_runs}"
        alt_score = f"{game.away.team_abbr} {away_runs}, {game.home.team_abbr} {home_runs}"
        if recap.final_score not in (expected_score, alt_score):
            report.errors.append(
                f"Recap for game {recap.game_id}: final_score '{recap.final_score}' does not match game data '{expected_score}'"
            )
```

### Publisher (full implementation in D7 above)

The `Publisher` class is fully defined in D7. The `GenerationOrchestrator` wiring is defined in D9.

---

## Migrations

There are no database migrations. The pipeline writes files and directories.

### First-run initialization

The `daily-sports-page` package includes a `scripts/init.sh` script that creates the required directory structure and copies config templates on first run:

```bash
#!/usr/bin/env bash
# scripts/init.sh
set -euo pipefail

mkdir -p build
mkdir -p config

for tpl in config/settings.yaml.example config/editorial.yaml.example config/schedules.yaml.example config/teams.yaml.example; do
  dest="${tpl%.example}"
  if [ ! -f "$dest" ]; then
    cp "$tpl" "$dest"
    echo "Created $dest"
  fi
done

echo "Init complete. Edit config/*.yaml before running the pipeline."
```

The CLI also checks for missing config files on startup and prints actionable guidance if they are absent.

### Build artifact organization and aging

Each pipeline run writes to `build/<edition-id>/`. These directories are not automatically deleted — they serve as a debugging and audit trail. A cron job or manual cleanup script ages out build directories older than 30 days:

```python
# scripts/cleanup_builds.py
import shutil
import time
from pathlib import Path

BUILD_DIR = Path("build")
MAX_AGE_DAYS = 30

for edition_dir in BUILD_DIR.iterdir():
    if not edition_dir.is_dir():
        continue
    age_days = (time.time() - edition_dir.stat().st_mtime) / 86400
    if age_days > MAX_AGE_DAYS:
        shutil.rmtree(edition_dir)
        print(f"Removed {edition_dir}")
```

### Archive file naming convention

Published editions are archived to `/daily-sports-page/archive/YYYY-MM-DD-HHMM.html` where `HHMM` is the edition ID's time component in America/New_York. For example:

```text
/daily-sports-page/archive/2026-07-13-0600.html   ← morning edition
/daily-sports-page/archive/2026-07-13-1200.html   ← midday edition
/daily-sports-page/archive/2026-07-13-1800.html   ← evening edition
/daily-sports-page/archive/2026-07-13-2200.html   ← late edition
/daily-sports-page/archive/2026-07-14-0130.html   ← final edition
```

Archive files are plain HTML and carry no special cache headers. They are not linked from the live page by default but serve as a historical record accessible by URL.

---

## Testing Philosophy

### Unit tests — normalization

Every mapping in the `Normalizer` is tested in isolation. The `_GAME_STATUS_MAP` is exhaustively covered — every known detailedState string from the MLB Stats API maps to the correct `GameStatus` enum value. The `_parse_game` method is tested with fixture JSON copied verbatim from the API for a final game, an in-progress game, a postponed game, and a doubleheader. Normalization tests do not make network calls.

### Unit tests — statistics

The `StatisticsProcessor.detect_notable_performances` method is tested against synthetic `Game` fixtures: a game ending in a bottom-of-ninth walk-off home run (walk-off tag + score boost), a 12-inning game (extra-inning tag), a final with a 10-run differential (no drama boost), and a game with no linescore data (graceful fallback). Sorting order is tested separately from tag detection.

### Unit tests — lead-story scoring

The `score_game` function is tested with each weight in isolation — one scenario activating only the playoff weight, one activating only historic weight — to verify that each weight contributes exactly its configured value. Manual overrides are tested to confirm they bypass the formula entirely. A test verifies that a game with a manual override score of 0.0 is ranked last even if the formula would score it highly.

### Unit tests — HTML escaping

The Jinja2 environment is tested with a synthetic Edition containing a game where the team name contains `<script>alert(1)</script>`. The rendered HTML is parsed by BeautifulSoup and the script tag must not be present as a DOM element. All free-text fields (headline, deck, paragraphs, injury descriptions, transaction explanations) are covered with adversarial XSS inputs.

### Integration tests — provider to Edition JSON

Integration tests load fixture JSON files from `tests/fixtures/` representing real API responses and run the full collect → normalize → generate chain against them. The output Edition JSON is validated against the Pydantic schema. These tests run without network access, substituting fixture files for live API calls. A test covers the degraded mode: schedule fixture is present, standings fixture is missing, edition is generated with `standings: null` and a freshness warning.

### Snapshot tests

Snapshot tests cover a curated set of representative fixtures and assert that the rendered HTML matches a committed reference file. Any intentional change to the template requires updating the snapshot. Snapshots are stored in `tests/snapshots/`. Fixtures include: a full 15-game slate (all statuses present), a partial slate (5 games, some postponed), Opening Day (no prior-day results), a postseason game (ALDS Game 3), a doubleheader (two games same team same day), all games postponed, a 14-inning extra-inning game, a combined no-hitter, and a trade-deadline-day edition with 20+ transactions.

### Visual regression tests

Playwright tests render each snapshot fixture in a headless Chromium browser at four viewport sizes: 1440×1200 (wide desktop), 1024×768 (laptop), 768×1024 (tablet portrait), and 390×844 (iPhone 14 Pro). Screenshots are compared to committed reference images using Playwright's built-in comparison with a configurable pixel-difference threshold. Tests run in CI on pull requests. Visual regression failures require explicit approval to update reference images.

### Data accuracy tests

A dedicated test suite parses the rendered HTML with BeautifulSoup and verifies that key values in the DOM match the Edition JSON exactly. Checks include: every game score in the scoreboard matches `edition.games[*].home.runs` and `edition.games[*].away.runs`; every standings row PCT value matches `edition.standings.divisions[*].rows[*].pct`; the top-ranked batting average leader in the rendered table matches `edition.league_leaders.batting.avg[0].value`. These tests guard against template logic bugs that would silently display wrong numbers.

### Accessibility tests

Playwright tests run `axe-core` against the rendered page at desktop and mobile viewports. Zero critical or serious violations are required for CI to pass. Specific manual checks include: the skip link is the first focusable element; the league-leaders tab switcher passes keyboard navigation without focus traps; all data tables have visible `<caption>` elements; no `<img>` tags lack `alt` attributes.

---

## Documentation Plan

### `README.md`

**Audience:** Developers and operators setting up the project for the first time.

Cover the project description, prerequisites (Python 3.12+, pip, optional Node.js for asset builds), installation steps (`pip install -e ".[dev]"`), first-run initialization (`scripts/init.sh`), required environment variables (`OPENAI_API_KEY` or `ANTHROPIC_API_KEY` for AI generation, optional), and the quickstart command sequence: `daily-sports-page run --dry-run`. Include a brief description of each CLI command and a link to `docs/dev/pipeline.md` for full detail.

### `docs/dev/pipeline.md`

**Audience:** Developers working on the generation pipeline.

Document each pipeline stage in sequence: what it consumes, what it produces, where output is written, and how to run it independently via CLI. Explain how to use `daily-sports-page render --edition-json path/to/edition.json` to re-render any historical edition without API calls. Document the `build/<edition-id>/` directory structure and what each file represents. Cover the degraded mode: which stages are skippable, what happens when a provider is unavailable, and how to verify the `run.json` observability record.

### `docs/dev/edition-schema.md`

**Audience:** Developers writing templates or tools that consume Edition JSON.

Document the full Edition JSON schema with field descriptions, types, and examples. Include the `EditionType` and `EditionStatus` enumerations with descriptions of each value. Document the `GameStatus` enum, the `TransactionType` enum, `RosterStatus`, and `InjuryConfidence`. Provide a complete example Edition JSON (redacted to a 3-game sample). Document the `generationMetadata` and `dataFreshness` structures and explain how freshness warnings are surfaced on the page.

### `docs/dev/rendering.md`

**Audience:** Developers modifying the page design or templates.

Document the Jinja2 template structure: `templates/index.html.j2` as the root, the `sections/` partial includes, the `games/` sub-partials. Explain the `asset()` global function and how to register new versioned static assets. Cover the CSS and JS build step (esbuild, PostCSS) and how to add new styles or scripts. Document the `autoescape=True` environment and how to safely pass pre-rendered HTML (using Jinja2's `Markup`). Cover snapshot test updating when templates change.

### `docs/dev/publishing.md`

**Audience:** Operators deploying and maintaining the pipeline.

Document the CDN origin directory structure, the `Cache-Control` header strategy (60-second max-age for `index.html`, immutable for versioned assets), and how to configure the `cdn_purge_hook`. Cover the atomic publication process step by step. Document the rollback procedure (`publisher.rollback()` or manual: `cp index.html.lkg index.html`). Explain the archive convention. Document the cron schedule format in `config/schedules.yaml` and how to set up the pipeline as a systemd timer or cron job.

### `docs/ops/monitoring.md`

**Audience:** Operators monitoring the service in production.

Document the structured JSON run log format (`run.json`) and all fields in `GenerationRun`. Explain the `final_status` values and what each means operationally. Cover the freshness warning thresholds from `config/settings.yaml` and how they surface on the page as visible banners. Describe the recommended alerting setup: alert on `final_status == "failed"`, alert if no edition has been published in the last 4 hours, and alert if the live `index.html` mtime is older than the schedule interval. Provide example log parsing queries.

---

## Risks / Trade-offs

### AI hallucination risk

**Risk:** The AI provider generates prose that invents a quote, attributes a statistic incorrectly, mentions a player who did not play in the game, or implies a standings implication that is not grounded in the supplied data. Hallucinated content on a sports publication erodes reader trust and can spread misinformation.

**Mitigation:** AI prompts include only structured facts from the Edition JSON — no free-form instructions that invite speculation. The prompt explicitly forbids inventing quotes, transactions, attendance, or return timelines. The `ContentValidator` checks the AI output's `factsUsed` field against the Edition JSON and fails validation if any claim cannot be mapped to a source record. Deterministic fallback templates guarantee that the pipeline always publishes accurate scores and outcomes even when AI output is rejected. The AI output format is structured JSON (`{"headline", "deck", "paragraphs", "factsUsed"}`) — not raw prose — which makes automated fact-checking tractable.

### Data provider dependency

**Risk:** The MLB Stats API is an unofficial, undocumented API with no SLA. It may change its response schema, rate-limit the pipeline, or be unavailable during peak game times. Provider outages would leave the pipeline unable to generate fresh editions.

**Mitigation:** HTTPX + Tenacity retry logic handles transient failures with exponential backoff. The response cache stores the last successful response for each data type; if a provider is unavailable, the pipeline uses cached data within configurable max-age thresholds. The cache age for live scores (5 min) is more aggressive than for standings (30 min) or league leaders (6 hours), reflecting data volatility. If cached data is also stale, the pipeline publishes a degraded edition with a visible freshness warning on the page. The Pydantic normalizer is isolated — if the API changes a field name, the normalization layer absorbs the error without propagating it to the renderer.

### Large page size with many games

**Risk:** On days with 15 games (all 30 teams playing), the HTML output could approach or exceed the 500 KB budget. Each game has a linescore table, probable pitchers, TV information, and a full game recap with multiple paragraphs. Standings, league leaders, and transactions add further bulk.

**Mitigation:** The HTML budget is enforced by a post-render check in the pipeline. If the rendered file exceeds 500 KB, the pipeline logs a warning and fails (in strict mode) before publishing. Template design should use CSS rather than repeated inline markup for table styling. League leaders are rendered as a single table with JavaScript-powered tab switching — all categories are present in the DOM but only one tab is visible at a time, avoiding duplicate markup. Game recaps are ordered and the template can be configured to include only the top N recaps in full, with remaining games showing score-only summaries.

### Atomic rename on CDN-backed storage

**Risk:** On some CDN configurations, the web root is not a standard POSIX filesystem but a FUSE mount, an NFS share, or a CDN-managed object store. POSIX atomic rename semantics are not guaranteed on all of these. A failed rename that leaves a partial write would serve a corrupt page.

**Mitigation:** The `Publisher` uses `tmp.rename(dest)` which is atomic on POSIX local filesystems — the most common deployment target (a VPS with nginx serving files from disk). For object-store origins (S3, R2, GCS), the publish step must be replaced with an atomic `PUT` using the provider SDK — the `Publisher` class is designed to be subclassed for this purpose. Operators deploying to object storage should implement an `S3Publisher` that uses a versioned `PUT` followed by an alias update. This is documented in `docs/dev/publishing.md` but not implemented in the initial release.

### Editorial scoring subjectivity

**Risk:** The lead-story scoring formula is configurable, but it still encodes a value judgment about what constitutes a significant baseball game. A low-scoring pitcher's duel may be as significant as a high-scoring walk-off for some audiences but score lower under the current formula. Manual editorial staff may disagree with the algorithm's choices on any given day.

**Mitigation:** Manual lead overrides in `config/editorial.yaml` allow any game to be pinned to lead at any time without redeployment. The scoring weights are YAML-configurable, not hardcoded. The `run.json` record captures the final lead score for every game, giving editorial staff visibility into how the algorithm ranked games so they can tune weights or apply overrides. Over time, the weights can be calibrated against editorial retrospectives.

### CSS and JS budget discipline

**Risk:** As the page grows in features — tabs, responsive layouts, freshness banners, mobile typography — the CSS and JS bundles will grow. It is easy to exceed the 100 KB compressed budget per bundle without noticing until a performance regression appears in CI.

**Mitigation:** Bundle size checks are enforced by the pipeline after the frontend asset build step. If `main.min.js` or `main.css` (post-PostCSS, post-compression) exceed 100 KB, the pipeline fails with a clear error before publishing. esbuild reports uncompressed bundle sizes; the pipeline uses gzip-compressed size for the budget check. CSS is scoped tightly to the newspaper design — no utility-class framework is used. JavaScript is limited to the tab switcher, freshness timestamp display, and any progressive enhancement. Any new JavaScript feature must be reviewed against the budget before merging.

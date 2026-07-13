## Why

SportzBallz needs an automated, newspaper-style MLB publication that delivers scores, standings, recaps, league leaders, transactions, and editorial content as a pre-generated static HTML page — several times per day — without requiring a runtime application server, client-side API calls, or user accounts. There is currently no such product; this is a greenfield build.

## What Changes

- **New**: A Python-based static-site generation pipeline that collects MLB data, normalizes it, scores editorial significance, generates AI-assisted editorial content, validates everything, renders to static HTML, and publishes atomically to `https://sportzballz.io/daily-sports-page/index.html`
- **New**: A structured Edition JSON data model that decouples data collection from HTML rendering
- **New**: A newspaper-style HTML/CSS design system (serif typography, multi-column layout, print stylesheet, responsive breakpoints)
- **New**: A configurable publication schedule (cron-compatible, America/New_York, with manual trigger support)
- **New**: An atomic publication process with rollback, last-known-good preservation, and CDN cache purge
- **New**: Observability — structured generation run logs, failure alerts, and per-run metrics
- **New**: A CLI (`daily-sports-page`) exposing `collect`, `normalize`, `generate`, `validate`, `render`, `publish`, and `run` subcommands

## Capabilities

### New Capabilities

- `edition-model`: The Edition JSON schema — root data model for all content including metadata, games, standings, league leaders, stories, transactions, injuries, and generation provenance
- `data-collection`: MLB sports data collection — HTTP clients, retry/backoff, raw-response caching, provider timestamp tracking, team/player identifier mapping
- `normalization`: Transforms raw provider responses into canonical internal models — standardizes IDs, game states, date/time formats, deduplication, and conflict resolution
- `statistics`: Calculates standings, ranks league leaders, determines player qualification, derives game metrics, detects notable performances and milestones
- `editorial-pipeline`: Selects lead story via configurable scoring model, selects secondary stories, drives AI generation of recaps and league summaries, attaches source facts, provides deterministic fallback copy when AI is unavailable
- `content-validation`: Validates AI and editorial output against source facts — score cross-checks, player/team relationships, unsupported-claim detection, duplicate-content detection, publication blocking rules
- `html-renderer`: Jinja2 templates that consume Edition JSON and produce newspaper-style static HTML — masthead, all required sections, league-leader tab interactions, print stylesheet, semantic HTML, WCAG 2.2 AA accessibility
- `publishing-pipeline`: Atomic build-validate-publish workflow, archive support, CDN purge hook, rollback to last-known-good, staging/production configuration
- `generation-scheduler`: Configurable cron-based publication schedule (America/New_York), manual trigger, event-triggered runs (post-game, post-transaction)
- `observability`: Structured run logs, per-phase timing, provider failure tracking, publication status recording, failure alerting

### Modified Capabilities

## Impact

- **New repository** (`daily-sports-page/`) following the structure defined in the requirements
- **Python 3.12+** primary language; Pydantic models, Jinja2 templates, HTTPX clients, Tenacity retry, JSON Schema validation, Pytest, Playwright, Ruff, MyPy
- **Optional Node.js tooling** for CSS processing (PostCSS / Lightning CSS), JS bundling (esbuild), HTML linting (HTMLHint)
- **External dependencies**: MLB data provider API (credentials from environment), AI provider API (credentials from environment)
- **Deployment**: Static files served from `sportzballz.io`; no application server required for page delivery; generation pipeline runs on a scheduled host or CI/CD system
- **No breaking changes** — this is a new, standalone product with no existing consumers

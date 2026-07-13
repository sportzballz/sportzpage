## 1. Repository and Project Setup

- [x] 1.1 Create repository directory structure (`src/`, `config/`, `templates/`, `static/`, `prompts/`, `schemas/`, `tests/`, `build/`, `scripts/`)
- [x] 1.2 Configure `pyproject.toml` with Python 3.12+, Pydantic v2, Jinja2, HTTPX, Tenacity, Typer, Pytest, Ruff, MyPy dependencies
- [x] 1.3 Configure `package.json` with optional Node.js tooling (esbuild, PostCSS, Lightning CSS, Prettier, HTMLHint)
- [x] 1.4 Write `config/settings.yaml` template with all configurable values (schedule, timezone, output path, base URL, freshness limits, feature flags)
- [x] 1.5 Write `config/editorial.yaml` template with lead-story scoring weights and manual override fields
- [x] 1.6 Write `config/schedules.yaml` template with default America/New_York schedule (06:00, 12:00, 17:00, 23:30)
- [x] 1.7 Write `config/teams.yaml` with canonical MLB team ID mappings (all 30 teams)
- [x] 1.8 Set up Ruff and MyPy configuration in `pyproject.toml`
- [x] 1.9 Initialize `.github/workflows/` with CI workflow (lint, type-check, test)

## 2. Domain Models and Schemas

- [x] 2.1 Implement `GameStatus` enum (final, in_progress, delayed, postponed, suspended, scheduled)
- [x] 2.2 Implement `Pitcher` Pydantic model (name, handedness, record, ERA, confirmationStatus)
- [x] 2.3 Implement `Game` Pydantic model (all required fields per spec: away/home team, scores, status, inning, outs, pitchers, startTime, ballpark, doubleheader, postponementReason, recapAnchor)
- [x] 2.4 Implement `StandingsRow` Pydantic model (team, W, L, PCT, GB, wcGB, last10, streak, homeRecord, awayRecord, runDifferential)
- [x] 2.5 Implement `LeaderEntry` and `LeagueLeaders` Pydantic models (all 13 batting + 15 pitching categories)
- [x] 2.6 Implement `Story` Pydantic model (headline, deck, byline, body, primaryImage, caption, sourceDataReferences, storyType, teams, players, factsUsed)
- [x] 2.7 Implement `GameRecap` Pydantic model (extends Story with gameId, finalScore, winningPitcher, losingPitcher, save, tags enum)
- [x] 2.8 Implement `TransactionType` enum and `Transaction` Pydantic model (all 11 transaction types)
- [x] 2.9 Implement `Injury` Pydantic model with confidence level enum; MUST NOT allow invented return dates
- [x] 2.10 Implement `HistoricalItem` Pydantic model
- [x] 2.11 Implement `DataFreshness` Pydantic model (per-section update timestamps)
- [x] 2.12 Implement `EditionMetadata` Pydantic model (id, type, date, generatedAt, dataCurrentThrough, timezone, status)
- [x] 2.13 Implement root `Edition` Pydantic model composing all sub-models
- [x] 2.14 Implement `GenerationRun` Pydantic model (runId, editionId, startTime, completionTime, phase durations, providerStatuses, finalStatus enum)
- [x] 2.15 Write `schemas/edition.schema.json` JSON Schema file for Edition
- [x] 2.16 Write `schemas/editorial.schema.json` JSON Schema file for editorial content
- [x] 2.17 Write unit tests for all model validation rules

## 3. Data Collection

- [x] 3.1 Implement `Collector` abstract base class (interface: `collect() → RawProviderResponse`)
- [x] 3.2 Implement `ResponseCache` (filesystem-based, configurable TTL per data type, provider timestamp recording)
- [x] 3.3 Implement `MLBCollector` with HTTPX async client and Tenacity exponential backoff retry
- [x] 3.4 Implement authentication handling via environment variables (no committed secrets)
- [x] 3.5 Implement team identifier mapping to canonical internal IDs (using `config/teams.yaml`)
- [x] 3.6 Implement player identifier mapping to canonical internal IDs
- [x] 3.7 Implement stale-cache detection against configurable max-age thresholds
- [x] 3.8 Implement fixture generation mode (saves raw responses as test fixtures)
- [x] 3.9 Write unit tests for retry logic, cache behavior, stale-cache handling
- [ ] 3.10 Generate representative test fixtures: full 15-game slate, partial slate, postponements, doubleheader, no-hitter scenario

## 4. Normalization

- [x] 4.1 Implement `Normalizer` class that converts raw provider responses to canonical Pydantic models
- [x] 4.2 Implement game status value mapping to `GameStatus` enum
- [x] 4.3 Implement date/time normalization to ISO 8601 with timezone
- [x] 4.4 Implement cross-provider deduplication by canonical game/player/team ID
- [x] 4.5 Implement conflict resolution using configurable provider priority rules
- [x] 4.6 Write unit tests for team normalization, player normalization, date conversion, game-state mapping, deduplication, conflict resolution

## 5. Statistical Processing

- [x] 5.1 Implement `StatisticsProcessor` class
- [x] 5.2 Implement standings calculation for all 6 divisions (W, L, PCT, GB, last10, streak, home/away records, run differential)
- [x] 5.3 Implement wild-card standings (AL and NL, games behind)
- [x] 5.4 Implement league-leader ranking for all 13 batting categories
- [x] 5.5 Implement league-leader ranking for all 15 pitching categories
- [x] 5.6 Implement player qualification rules (PA-per-team-game for batters, IP-per-team-game for pitchers)
- [x] 5.7 Implement derived game metrics (comeback size, margin, extra-inning flag, walk-off flag, no-hitter status)
- [x] 5.8 Implement notable-performance detection (record-setting, milestone-approaching, no-hitter)
- [x] 5.9 Implement editorial ranking signal generation (inputs to lead-story scorer)
- [x] 5.10 Write unit tests for standings calculations, top-10 ranking, qualification rules, walk-off detection, comeback detection

## 6. Editorial Pipeline

- [x] 6.1 Implement `EditorialEngine` class
- [x] 6.2 Implement configurable lead-story scoring model (`playoff_weight + historic_weight + performance_weight + game_drama_weight + national_interest_weight + recency_weight`)
- [x] 6.3 Implement manual editorial override support (lead_story_game_id, featured_player_ids, suppress_story_ids from `editorial.yaml`)
- [x] 6.4 Implement secondary story selection (3–6 stories)
- [x] 6.5 Implement AI generation prompt builders for: lead story, game recaps, around-the-league items, headlines
- [x] 6.6 Write prompt templates in `prompts/` directory (lead-story.md, game-recap.md, league-roundup.md, headline.md)
- [x] 6.7 Implement AI provider client (structured JSON output, `factsUsed` attachment)
- [x] 6.8 Implement deterministic fallback templates for all AI-generated sections
- [x] 6.9 Implement game-recap editorial tags (walk-off, extra-inning, comeback, upset, best-pitching, highest-scoring, standings-impact)
- [x] 6.10 Implement editorial neutrality enforcement (no single-team bias in front-page selection)
- [x] 6.11 Write unit tests for lead-story scoring, manual override, secondary story selection, fallback template generation

## 7. Content Validation

- [x] 7.1 Implement `ContentValidator` class
- [x] 7.2 Implement score cross-validation (editorial content vs Edition JSON game records)
- [x] 7.3 Implement player-team relationship validation
- [x] 7.4 Implement statistic value validation (cited stats vs Edition JSON leaders data)
- [x] 7.5 Implement unsupported-claim detection (assertions not in `factsUsed`)
- [x] 7.6 Implement duplicate-text detection across stories
- [x] 7.7 Implement required-field validation (headline, body non-empty)
- [x] 7.8 Implement injury return-date invention detection (reject AI-invented return dates)
- [x] 7.9 Implement publication-blocking rules (failed validation blocks publish, triggers alert)
- [x] 7.10 Write unit tests for all validation rules; write integration test for AI output validation

## 8. HTML Renderer

- [ ] 8.1 Implement `HTMLRenderer` class with Jinja2 environment setup
- [ ] 8.2 Write `templates/index.html.j2` master template (semantic HTML5, all required section IDs)
- [ ] 8.3 Write `templates/sections/masthead.html.j2` (publication name, edition type, date, generatedAt, dataCurrentThrough, timezone — separate fields)
- [ ] 8.4 Write `templates/sections/scoreboard.html.j2` (grouped by status, compact newspaper style)
- [ ] 8.5 Write `templates/sections/todays-games.html.j2` (probable pitchers, handedness, ERA, weather, TV info, confirmation status)
- [ ] 8.6 Write `templates/sections/standings.html.j2` (all 6 divisions + wild cards; responsive: core columns always visible)
- [ ] 8.7 Write `templates/sections/league-leaders.html.j2` (all categories embedded; JS tab switching degrades gracefully)
- [ ] 8.8 Write `templates/sections/game-recaps.html.j2` (editorial-significance ordered; recap tags)
- [ ] 8.9 Write `templates/sections/around-the-league.html.j2`
- [ ] 8.10 Write `templates/sections/transactions.html.j2`
- [ ] 8.11 Write `templates/sections/injuries.html.j2` (confidence levels; no invented return dates)
- [ ] 8.12 Write `templates/sections/history.html.j2`
- [ ] 8.13 Write `static/css/daily-sports-page.css` (serif typography, multi-column layout, compact tables, drop caps, horizontal rules, restrained palette, newsprint background; responsive breakpoints for 1440/1024/768/390)
- [ ] 8.14 Write `@media print` stylesheet (black on light, no interactive controls, no orphaned headlines, letter-size format)
- [ ] 8.15 Write `static/js/daily-sports-page.js` (<100 KB compressed; league-leader tabs, section collapse, copy-link, print controls; all progressive enhancement)
- [ ] 8.16 Implement SEO metadata rendering (title, meta description, canonical URL, Open Graph, `sportzballz-edition-id` meta tag)
- [ ] 8.17 Implement `data/edition.json` output alongside HTML
- [ ] 8.18 Implement HTML escaping for all text content; verify no raw HTML injection from AI output
- [ ] 8.19 Verify HTML output is deterministic for identical Edition JSON input
- [ ] 8.20 Write snapshot tests for full and partial game slates; verify all required section IDs present
- [ ] 8.21 Verify core content readable with JavaScript disabled (manual + automated test)

## 9. Publishing Pipeline

- [ ] 9.1 Implement `Publisher` class
- [ ] 9.2 Implement temp-directory build flow (all output to `/tmp/daily-sports-page-build-<id>/`)
- [ ] 9.3 Implement pre-publication validation checklist (required files, HTML syntax, internal links, section IDs, timestamp)
- [ ] 9.4 Implement asset-first upload/copy (assets before `index.html`)
- [ ] 9.5 Implement atomic `index.html` replacement (filesystem rename or platform equivalent)
- [ ] 9.6 Implement post-publication URL verification
- [ ] 9.7 Implement CDN cache purge hook (configurable, no-op when not configured)
- [ ] 9.8 Implement last-known-good edition tracking (path + edition ID + timestamp)
- [ ] 9.9 Implement rollback to last-known-good
- [ ] 9.10 Implement archive file creation at `/daily-sports-page/archive/YYYY-MM-DD-HHMM.html`
- [ ] 9.11 Implement staging vs production configuration targets
- [ ] 9.12 Write scripts: `scripts/generate-edition.sh`, `scripts/publish-edition.sh`, `scripts/validate-edition.sh`
- [ ] 9.13 Write integration tests for: successful publication, failed validation blocking, rollback behavior, archive creation

## 10. Generation Scheduler and Orchestrator

- [ ] 10.1 Implement `GenerationOrchestrator` class (wires all pipeline stages, manages run state, handles degraded modes)
- [ ] 10.2 Implement AI-failure degraded mode (use deterministic templates; still publish scores/standings/schedule)
- [ ] 10.3 Implement data-provider-failure degraded mode (retry + cache fallback; mark stale sections)
- [ ] 10.4 Implement render-failure handling (abort, preserve current live edition, save artifacts, alert)
- [ ] 10.5 Implement concurrent run prevention (lock mechanism per publication target)
- [ ] 10.6 Implement stale-edition detection and page warning injection (when no publish within expected window)
- [ ] 10.7 Implement edition type assignment logic based on generation time and available data
- [ ] 10.8 Implement `config/schedules.yaml` parser and cron-based scheduler
- [ ] 10.9 Implement manual trigger support (CLI `run` command)
- [ ] 10.10 Implement event-triggered run support (post-game, post-transaction hooks)

## 11. CLI

- [ ] 11.1 Implement `daily-sports-page collect` command
- [ ] 11.2 Implement `daily-sports-page normalize` command
- [ ] 11.3 Implement `daily-sports-page generate` command
- [ ] 11.4 Implement `daily-sports-page validate` command
- [ ] 11.5 Implement `daily-sports-page render` command with `--edition-json` flag (renders from saved JSON, no API calls)
- [ ] 11.6 Implement `daily-sports-page publish` command
- [ ] 11.7 Implement `daily-sports-page run` command with `--edition morning/midday/evening/late`, `--date`, `--timezone`, `--publish`, `--dry-run` flags
- [ ] 11.8 Register `daily-sports-page` as a console script entry point in `pyproject.toml`

## 12. Observability

- [ ] 12.1 Implement structured JSON run logging (all required fields per spec: runId, editionId, all phase durations, provider statuses, game/story/category counts, validation results, published URL, final status)
- [ ] 12.2 Implement run status transitions (started → collecting → normalizing → generating → validating → rendering → publishing → published / failed / published_degraded)
- [ ] 12.3 Implement `published_degraded` status for partial success (AI failed but scores published)
- [ ] 12.4 Implement failure alerting (configurable channel; triggered on `failed` and optionally on `published_degraded`)
- [ ] 12.5 Implement last-known-good tracking update on successful publication
- [ ] 12.6 Implement edition health report (per-section freshness vs configured max-age thresholds)
- [ ] 12.7 Write unit tests for status transitions and alert triggering

## 13. Testing and QA

- [ ] 13.1 Write representative fixtures for all snapshot test scenarios (Opening Day, All-Star break, postseason, doubleheader, postponements, extra-inning games, no-hitter, trade deadline, no scheduled games)
- [ ] 13.2 Write full integration test: provider response → normalized model → edition JSON → HTML
- [ ] 13.3 Write Playwright visual regression tests at all 4 required viewports (1440×1200, 1024×1366, 768×1024, 390×844)
- [ ] 13.4 Write data accuracy tests (compare rendered values vs edition JSON for scores, team names, standings, league leaders, pitcher decisions, game status, dates/times)
- [ ] 13.5 Write accessibility checks (WCAG 2.2 AA; skip-to-content link; ARIA on league-leader tabs; contrast; keyboard navigation)
- [ ] 13.6 Write broken-link checks for generated HTML
- [ ] 13.7 Verify print layout visually (letter-size, no orphaned headlines, no interactive controls)
- [ ] 13.8 Confirm HTML output < 500 KB on a full 15-game slate
- [ ] 13.9 Confirm JS bundle < 100 KB compressed; CSS < 100 KB compressed

## 14. Documentation

- [ ] 14.1 Write `README.md` (quickstart, requirements, environment variables, quick-run example)
- [ ] 14.2 Write `docs/dev/pipeline.md` (generation pipeline stages, how to run each stage independently, `--edition-json` dry-run usage)
- [ ] 14.3 Write `docs/dev/edition-schema.md` (Edition JSON schema reference for all fields)
- [ ] 14.4 Write `docs/dev/rendering.md` (Jinja2 template system, CSS design system, how to modify layout or style)
- [ ] 14.5 Write `docs/dev/publishing.md` (deployment targets, CDN configuration, atomic publish, rollback procedure)
- [ ] 14.6 Write `docs/ops/monitoring.md` (structured logs, alerting setup, freshness thresholds, how to interpret health reports)

## 15. MVP Acceptance Verification

- [ ] 15.1 Verify automated `daily-sports-page run` generates a valid static MLB edition end-to-end
- [ ] 15.2 Verify published page loads at the target URL and contains all required sections
- [ ] 15.3 Verify all scheduled and completed games appear in the scoreboard
- [ ] 15.4 Verify current standings are present for all 6 divisions and wild cards
- [ ] 15.5 Verify top 10 league leaders are present for all required batting and pitching categories
- [ ] 15.6 Verify lead story and all recaps cite traceable `factsUsed` references
- [ ] 15.7 Verify every score and statistic displayed traces to a value in `edition.json`
- [ ] 15.8 Verify page is fully readable with JavaScript disabled
- [ ] 15.9 Verify page functions on current Chrome, Edge, Firefox, Safari, Mobile Safari, Chrome for Android
- [ ] 15.10 Verify page prints cleanly to letter-size (no broken tables, no orphaned headlines)
- [ ] 15.11 Verify a failed run does not replace the last successful edition
- [ ] 15.12 Verify publication timestamp and data cutoff are both visible and are distinct fields
- [ ] 15.13 Verify the generation pipeline records a clear published or failed status
- [ ] 15.14 Verify no Philadelphia-first or any single-team personalization in front-page story selection

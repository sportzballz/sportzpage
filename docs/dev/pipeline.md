# Pipeline

The SportzBallz Daily Sports Page generator runs six sequential stages. Each stage can fail independently, and most support degraded-mode fallbacks.

---

## Stage Overview

```
┌─────────┐    ┌───────────┐    ┌──────────┐    ┌──────────┐    ┌────────┐    ┌─────────┐
│ collect │───▶│ normalize │───▶│ generate │───▶│ validate │───▶│ render │───▶│ publish │
└─────────┘    └───────────┘    └──────────┘    └──────────┘    └────────┘    └─────────┘
     │                │                │               │               │             │
  MLB API         Pydantic          AI + fallback   fact-check     Jinja2        atomic
  cache to        domain             Edition obj    gate            static        rename +
  build/cache/    models                            (hard stop)     HTML          CDN purge
```

---

## Stage 1: collect

**Class:** `src.collector.MLBCollector`

Hits the MLB Stats API and writes raw JSON responses to `build/cache/`. The cache is keyed by date and endpoint, so subsequent runs skip already-fetched data unless `--force-refresh` is passed.

**Behavior:**

- Retries failed requests with exponential backoff (default: 3 retries, base delay 1 s)
- Raises `CollectorError` after exhausting retries
- In fixture dump mode (`--fixture-dump`), writes responses to `tests/fixtures/` for use in offline tests

**Endpoints fetched per run:**

- `schedule` — games for the target date
- `linescore` — inning-by-inning scores for in-progress and completed games
- `boxscore` — pitchers, batting lines
- `standings` — all division standings
- `stats/leaders` — batting and pitching leader categories
- `transactions` — trades, signings, DFA, recalls (rolling 3-day window)
- `injuries` — active IL entries

**Run collect only:**

```bash
daily-sports-page collect --date 2026-07-13
```

---

## Stage 2: normalize

**Class:** `src.normalizer.Normalizer`

Converts raw API response dicts into typed Pydantic domain models (`src/models/`). This stage is the single source of truth for field names, types, and default values used throughout the rest of the pipeline.

**Behavior:**

- Deduplicates game entries (doubleheaders can appear in both schedule and linescore responses)
- Maps team IDs to abbreviations and full names via `config/teams.yaml`
- Emits a `NormalizedData` object consumed by `generate`
- Logs and skips malformed records rather than raising; a summary of skipped records appears in `generationMetadata.dataFreshness`

**Run normalize only (from cached data):**

```bash
daily-sports-page normalize --date 2026-07-13
```

---

## Stage 3: generate

**Class:** `src.editorial.EditorialEngine`

Selects the lead story, builds prompts, calls the AI provider, and assembles a complete `Edition` object.

**Behavior:**

1. Scores games using a priority function (walk-off > blowout > playoff implications > rivalry > close game)
2. Identifies the top-scoring game as the lead story candidate
3. Builds a structured prompt from the game data and injects relevant facts (pitching lines, key plays, standings context)
4. Calls the configured AI provider (OpenAI or Anthropic) with the prompt
5. Parses the structured response into `Story` objects
6. Falls back to deterministic template-based text if the AI call fails or returns malformed output (see [Degraded Mode](#degraded-mode))
7. Assembles the final `Edition` object including all sections

**Run generate only (requires normalized data in `build/cache/`):**

```bash
daily-sports-page generate --date 2026-07-13
```

---

## Stage 4: validate

**Class:** `src.validator.ContentValidator`

Cross-checks all editorial content against the normalized source facts before allowing publication.

**Checks performed:**

- All scores mentioned in headlines and body text match `game.homeScore` / `game.awayScore`
- All player names cited in stories exist in the `game` or `leagueLeaders` data
- No story references a game with `status: postponed` as if it were played
- `edition.dataCurrentThrough` is not older than the configured max staleness threshold

**Behavior:**

- Hard stop on validation failure — pipeline aborts and does **not** publish
- Failures are logged as structured events and trigger an alert if `ALERT_WEBHOOK_URL` is set
- All failures are written to `build/validate-failures-{run_id}.json` for review

---

## Stage 5: render

**Class:** `src.renderer.HTMLRenderer`

Takes the validated `Edition` object and renders it to static HTML using Jinja2 templates.

**Behavior:**

- Loads templates from `templates/`
- Writes `index.html` and `edition.json` to a staging directory (`build/{date}-{hhmm}/`)
- Output is deterministic: same `Edition` JSON always produces the same HTML
- Does not make any network calls

**Run render only from a saved edition JSON:**

```bash
daily-sports-page render --edition-json build/2026-07-13-0600/edition.json
```

See [`docs/dev/rendering.md`](rendering.md) for template structure details.

---

## Stage 6: publish

**Class:** `src.publisher.Publisher`

Atomically promotes the staged output to the live `OUTPUT_DIR`.

**Behavior:**

- Writes assets to a temp directory alongside `index.html`
- Validates the staged output (file existence, minimum size checks)
- Renames temp dir to live output path atomically
- Records the published edition ID and path in `{OUTPUT_DIR}/.lkg`
- Sends a POST to `CDN_PURGE_URL` if configured
- Archives the previous edition to `{OUTPUT_DIR}/archive/`

See [`docs/dev/publishing.md`](publishing.md) for atomic publish steps, rollback, and CDN configuration.

---

## Edition Types

Each edition type covers a different slice of the day. The `--edition` flag controls which type is generated.

| Edition type | Typical run time | Content emphasis                                                    |
| ------------ | ---------------- | ------------------------------------------------------------------- |
| `morning`    | 06:00–08:00      | Previous day final scores, standings update, overnight transactions |
| `midday`     | 11:00–13:00      | Morning game results, afternoon schedule preview                    |
| `evening`    | 17:00–19:00      | Afternoon results, evening game previews, standings                 |
| `late`       | 21:00–23:00      | In-progress evening games with live scores                          |
| `final`      | 00:00–02:00      | All final scores, complete standings, full transaction log          |
| `special`    | On demand        | Breaking news, trade deadline, postseason clinching                 |

If `--edition` is omitted, the runner selects the appropriate type based on the current time.

---

## Degraded Mode

The pipeline is designed to publish something rather than nothing when non-critical components fail.

| Failure                                       | Behavior                                                                                                   |
| --------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| AI provider returns error or malformed output | `EditorialEngine` falls back to deterministic Jinja2 templates; edition status set to `published_degraded` |
| MLB API endpoint fails after retries          | Use cached data if available; log staleness in `generationMetadata.dataFreshness`                          |
| Individual section data missing               | Section is omitted from edition; remaining sections publish normally                                       |
| `ContentValidator` fails                      | **Hard stop** — do not publish; alert triggered                                                            |
| Render fails                                  | **Hard stop** — keep current live edition; alert triggered                                                 |
| CDN purge fails                               | Log warning; do not abort publish; retry once                                                              |

In degraded mode, the live edition displays a banner:

> "Latest edition generated at [timestamp]. Some information may be delayed."

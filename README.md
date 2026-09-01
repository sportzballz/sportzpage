# SportzBallz Daily Sports Page

Automated MLB newspaper-style static site generator for SportzBallz.

## What It Does

SportzBallz Daily Sports Page pulls live data from the MLB Stats API, runs it through an AI-assisted editorial engine, and publishes a static HTML edition that looks and reads like a printed newspaper. Each edition covers:

- **Scores & recaps** — game results with AI-generated narrative recaps
- **Standings** — division standings and wild card races
- **League leaders** — batting average, home runs, ERA, strikeouts, and more
- **Transactions** — signings, trades, DFA, recalls, options
- **Injuries** — roster status, expected return timelines

Editions can be generated multiple times per day (morning, midday, evening, late, final) and published as static HTML to any file path or CDN-backed directory.

---

## Requirements

- **Python 3.12+**
- **Node.js** (optional — required only for asset bundling)

The native iPhone and iPad reader is in [`ios/`](ios/README.md). It downloads the live daily edition feeds, so routine newspaper publishing does not require an App Store update.

---

## Quick Setup

```bash
# 1. Clone the repo
git clone https://github.com/sportzballz/daily-sports-page.git
cd daily-sports-page

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\activate        # Windows

# 3. Install the package with dev dependencies
pip install -e ".[dev]"

# 4. Copy the environment variable template
cp .env.example .env
# Then open .env and fill in your values
```

---

## Environment Variables

Copy `.env.example` to `.env` and set the following:

| Variable            | Required | Default                                    | Description                                                    |
| ------------------- | -------- | ------------------------------------------ | -------------------------------------------------------------- |
| `MLB_API_KEY`       | Yes      | —                                          | MLB Stats API key (or equivalent data provider)                |
| `AI_API_KEY`        | Yes      | —                                          | AI provider key (OpenAI or Anthropic) for editorial generation |
| `OUTPUT_DIR`        | No       | `./build/output`                           | Directory where built editions are published                   |
| `PUBLIC_BASE_URL`   | No       | `https://sportzballz.io/daily-sports-page` | Public URL base used in canonical links and CDN purge paths    |
| `CDN_PURGE_URL`     | No       | —                                          | Webhook URL for CDN cache purge after publication              |
| `ALERT_WEBHOOK_URL` | No       | —                                          | Webhook URL for failure alerts                                 |

---

## Key Commands

### Full pipeline (collect → render → publish)

```bash
daily-sports-page run --edition morning --date 2026-07-13 --publish
```

### Dry run (no publish)

```bash
daily-sports-page run --dry-run
```

### Render from a saved edition JSON (no API calls)

```bash
daily-sports-page render --edition-json build/2026-07-13-0600/edition.json
```

### Collect data only

```bash
daily-sports-page collect --date 2026-07-13
```

### Normalize cached data only

```bash
daily-sports-page normalize --date 2026-07-13
```

### Rollback to last known good

```bash
daily-sports-page publish --rollback
```

### Run tests

```bash
python -m pytest
```

---

## Pipeline Overview

The generator runs six sequential stages:

```
collect → normalize → generate → validate → render → publish
```

| Stage         | What it does                                                               |
| ------------- | -------------------------------------------------------------------------- |
| **collect**   | Hits MLB Stats API; caches responses to `build/cache/`                     |
| **normalize** | Converts raw API responses to typed Pydantic domain models                 |
| **generate**  | Scores games, builds AI prompts, calls provider, outputs `Edition` object  |
| **validate**  | Cross-checks editorial content against source facts before publication     |
| **render**    | Jinja2 templates produce static HTML; writes `index.html` + `edition.json` |
| **publish**   | Atomic rename to output dir; preserves last-known-good; purges CDN         |

See [`docs/dev/pipeline.md`](docs/dev/pipeline.md) for full details on each stage, how to run stages independently, edition types, and degraded-mode behavior.

---

## Project Layout

```
daily-sports-page/
├── src/
│   ├── collector/          # MLBCollector and API clients
│   ├── normalizer/         # Normalizer and Pydantic domain models
│   ├── editorial/          # EditorialEngine, prompt builders, AI clients
│   ├── validator/          # ContentValidator
│   ├── renderer/           # HTMLRenderer and Jinja2 integration
│   ├── publisher/          # Publisher, LKG tracking, CDN purge
│   └── observability/      # Structured logging, health reports
├── templates/              # Jinja2 HTML templates
├── static/                 # CSS and JS assets
├── config/                 # settings.yaml, teams.yaml
├── tests/                  # pytest test suite
├── build/                  # Generated artifacts (gitignored)
│   ├── cache/              # API response cache
│   └── output/             # Default publish target
└── docs/
    ├── dev/                # Developer documentation
    └── ops/                # Operations documentation
```

---

## Further Reading

- [Pipeline details](docs/dev/pipeline.md)
- [Edition JSON schema](docs/dev/edition-schema.md)
- [Template system & rendering](docs/dev/rendering.md)
- [Publishing & CDN](docs/dev/publishing.md)
- [Monitoring & observability](docs/ops/monitoring.md)

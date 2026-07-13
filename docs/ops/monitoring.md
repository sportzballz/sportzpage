# Monitoring & Observability

Structured logging, run status, health reports, freshness thresholds, and alerting.

---

## Structured Log Format

Every pipeline run emits JSON log events to stdout (and optionally to a log file configured in `config/settings.yaml`). Each event is a single JSON object on one line.

**Event types:**

| Event            | When emitted                                     |
| ---------------- | ------------------------------------------------ |
| `run_start`      | Before collect begins                            |
| `phase_complete` | After each pipeline stage completes successfully |
| `run_complete`   | After publish succeeds                           |
| `run_failed`     | If any stage fails and the run is aborted        |

**Example: `run_start`**

```json
{
  "event": "run_start",
  "run_id": "a3f8c1d2",
  "edition_type": "morning",
  "date": "2026-07-13",
  "timestamp": "2026-07-13T06:42:00Z"
}
```

**Example: `phase_complete`**

```json
{
  "event": "phase_complete",
  "run_id": "a3f8c1d2",
  "edition_id": "2026-07-13-morning-a3f8c1",
  "phase": "collect",
  "duration_seconds": 4.21,
  "status": "ok",
  "timestamp": "2026-07-13T06:42:04Z"
}
```

**Example: `run_complete`**

```json
{
  "event": "run_complete",
  "run_id": "a3f8c1d2",
  "edition_id": "2026-07-13-morning-a3f8c1",
  "status": "published",
  "duration_seconds": 18.09,
  "timestamp": "2026-07-13T06:42:18Z"
}
```

**Example: `run_failed`**

```json
{
  "event": "run_failed",
  "run_id": "a3f8c1d2",
  "edition_id": "2026-07-13-morning-a3f8c1",
  "phase": "validate",
  "status": "failed",
  "error": "ContentValidationError: score mismatch in leadStory (game 716502)",
  "duration_seconds": 16.74,
  "timestamp": "2026-07-13T06:42:17Z"
}
```

### Key Log Fields

| Field              | Type   | Description                                                   |
| ------------------ | ------ | ------------------------------------------------------------- |
| `run_id`           | string | Short hex ID shared across all events for a single run        |
| `edition_id`       | string | Full edition identifier (absent in `run_start`)               |
| `phase`            | string | Pipeline stage name                                           |
| `duration_seconds` | float  | Wall-clock seconds for the phase or full run                  |
| `status`           | string | `ok`, `degraded`, `failed`, `published`, `published_degraded` |
| `timestamp`        | string | ISO 8601 UTC timestamp                                        |

---

## Run Status Lifecycle

A run transitions through these statuses in order:

```
started
  → collecting
  → normalizing
  → generating
  → validating
  → rendering
  → publishing
  → published
```

Terminal failure states:

```
* → failed
```

Degraded publish (AI failure, but scores/standings/schedule still published):

```
generating (ai_failed)
  → validating
  → rendering
  → publishing
  → published_degraded
```

### `published_degraded`

When the AI provider fails or returns malformed output, `EditorialEngine` falls back to deterministic Jinja2 templates for story text. The edition still publishes with scores, standings, league leaders, transactions, and injuries. The lead story and secondary stories contain factual summaries without narrative prose.

The live edition displays a banner:

> "Latest edition generated at [timestamp]. Some information may be delayed."

The `edition.status` field in `edition.json` is set to `published_degraded` so downstream consumers can distinguish this state.

---

## Health Report

The health report gives a per-section view of data freshness vs. configured thresholds.

```python
from src.observability.health import build_health_report, format_health_report

report = build_health_report(output_dir="/var/www/sports-page")
print(format_health_report(report))
```

**Example output:**

```text
SportzBallz Daily Sports Page — Health Report
Generated: 2026-07-13T07:15:00Z

Section            Last Updated          Age        Threshold   Status
─────────────────────────────────────────────────────────────────────────
Live Scores        2026-07-13T06:30Z     45m        5m          STALE
Scheduled Games    2026-07-13T06:28Z     47m        30m         STALE
Standings          2026-07-13T06:28Z     47m        30m         STALE
League Leaders     2026-07-13T06:28Z     47m        6h          OK
Transactions       2026-07-13T05:15Z     2h         30m         STALE
Injuries           2026-07-12T20:00Z     11h        2h          STALE
Historical         2026-07-13T00:00Z     7h         30d         OK

Last Successful Publish: 2026-07-13T06:42Z (edition: 2026-07-13-morning-a3f8c1)
```

---

## Default Freshness Thresholds

Thresholds are configured in `config/settings.yaml` under `freshness`:

```yaml
freshness:
  live_scores: 300 # 5 minutes
  scheduled_games: 1800 # 30 minutes
  standings: 1800 # 30 minutes
  league_leaders: 21600 # 6 hours
  transactions: 1800 # 30 minutes
  injuries: 7200 # 2 hours
  historical: 2592000 # 30 days
```

| Section         | Default threshold | Notes                                                  |
| --------------- | ----------------- | ------------------------------------------------------ |
| Live scores     | 5 min             | In-progress games; stale if no recent linescore update |
| Scheduled games | 30 min            | Start times, probable pitchers                         |
| Standings       | 30 min            | Division and wild card records                         |
| League leaders  | 6 hours           | Stat leaders update less frequently                    |
| Transactions    | 30 min            | Trades, DFAs, recalls, signings                        |
| Injuries        | 2 hours           | IL placements, status updates                          |
| Historical      | 30 days           | Career stats, historical records                       |

---

## Alerting

Set the `ALERT_WEBHOOK_URL` environment variable to receive failure notifications. The publisher POSTs the following JSON payload when a run ends in `failed` status:

```http
POST {ALERT_WEBHOOK_URL}
Content-Type: application/json

{
  "event": "run_failed",
  "run_id": "a3f8c1d2",
  "edition_id": "2026-07-13-morning-a3f8c1",
  "phase": "validate",
  "error": "ContentValidationError: score mismatch in leadStory (game 716502)",
  "timestamp": "2026-07-13T06:42:17Z",
  "output_dir": "/var/www/sports-page"
}
```

Alerts are also sent (with `event: cdn_purge_failed`) when a CDN purge fails, but the run status remains `published`.

**Webhook provider examples:**

| Provider  | Setup                                                                                |
| --------- | ------------------------------------------------------------------------------------ |
| PagerDuty | Use Events API v2 endpoint; wrap the payload in PagerDuty's envelope                 |
| Slack     | Use an Incoming Webhook URL; the payload is posted as-is to `#ops-alerts` or similar |
| Custom    | Any URL that accepts POST with a JSON body                                           |

---

## Checking the Last Successful Publish

```bash
cat {OUTPUT_DIR}/.lkg
```

Example output:

```json
{
  "edition_id": "2026-07-13-morning-a3f8c1",
  "path": "/var/www/sports-page/index.html",
  "published_at": "2026-07-13T06:42:55Z",
  "archive_path": "/var/www/sports-page/archive/2026-07-13-0642.html"
}
```

If `.lkg` is absent, no edition has ever been published to this output directory.

---

## Stale Edition Warning

If a successful publish has not occurred within the expected window for the current time of day, the rendered edition displays a banner at the top of the page:

> "Latest edition generated at 06:42 ET. Some information may be delayed."

This banner is controlled by the `edition.status` field and the `dataCurrentThrough` timestamp in `edition.json`. The Jinja2 template in `templates/sections/header.html.j2` renders the banner when either condition is true:

- `edition.status == "published_degraded"`
- `edition.dataCurrentThrough` is older than the configured `freshness.live_scores` threshold at render time

The banner does not affect any other part of the page and disappears automatically once a fresh edition is published and the CDN serves the new HTML.

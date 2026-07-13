# Edition JSON Schema

`edition.json` is written alongside `index.html` at publication time. It is the canonical record of everything in a published edition and can be used to re-render HTML at any time without API calls.

---

## Top-Level Structure

```json
{
  "edition": { ... },
  "games": [ ... ],
  "leadStory": { ... },
  "secondaryStories": [ ... ],
  "standings": { ... },
  "leagueLeaders": { ... },
  "transactions": [ ... ],
  "injuries": [ ... ],
  "generationMetadata": { ... }
}
```

---

## `edition` — Metadata

```json
{
  "id": "2026-07-13-morning-a3f8c1",
  "type": "morning",
  "date": "2026-07-13",
  "generatedAt": "2026-07-13T06:42:17Z",
  "dataCurrentThrough": "2026-07-13T06:30:00Z",
  "timezone": "America/New_York",
  "status": "published"
}
```

| Field                | Type   | Description                                                              |
| -------------------- | ------ | ------------------------------------------------------------------------ |
| `id`                 | string | Unique run identifier: `{date}-{type}-{hex}`                             |
| `type`               | string | Edition type: `morning`, `midday`, `evening`, `late`, `final`, `special` |
| `date`               | string | Target date in `YYYY-MM-DD` format                                       |
| `generatedAt`        | string | ISO 8601 UTC timestamp when generation completed                         |
| `dataCurrentThrough` | string | ISO 8601 UTC timestamp of the most recent data fetched                   |
| `timezone`           | string | IANA timezone used for display formatting                                |
| `status`             | string | `published` or `published_degraded`                                      |

---

## `games` — Game Array

Each element in the `games` array represents one MLB game.

```json
{
  "gameId": "716502",
  "awayTeam": "NYY",
  "awayTeamFull": "New York Yankees",
  "homeTeam": "BOS",
  "homeTeamFull": "Boston Red Sox",
  "awayScore": 4,
  "homeScore": 7,
  "status": "final",
  "inning": 9,
  "inningHalf": "bottom",
  "outs": 0,
  "awayStartingPitcher": "Gerrit Cole",
  "homeStartingPitcher": "Brayan Bello",
  "awayDecisionPitcher": "Gerrit Cole",
  "awayDecisionType": "L",
  "homeDecisionPitcher": "Brayan Bello",
  "homeDecisionType": "W",
  "startTime": "2026-07-12T23:10:00Z",
  "ballpark": "Fenway Park",
  "doubleheader": false,
  "doubleheaderGame": null,
  "postponementReason": null,
  "tags": ["rivalry", "walk-off"]
}
```

### `status` values

| Value         | Meaning                                   |
| ------------- | ----------------------------------------- |
| `scheduled`   | Game has not started                      |
| `warmup`      | Pre-game warmups underway                 |
| `in_progress` | Game is live                              |
| `final`       | Game completed normally                   |
| `final_extra` | Game completed in extra innings           |
| `postponed`   | Game postponed (see `postponementReason`) |
| `suspended`   | Game suspended mid-play                   |
| `cancelled`   | Game cancelled, will not be made up       |

### `tags` values

Computed by the editorial engine. Used for lead story scoring.

`walk-off`, `extra_innings`, `shutout`, `no_hitter`, `perfect_game`, `blowout`, `rivalry`, `playoff_implications`, `division_clinch`, `wild_card_clinch`

---

## `leadStory` / `secondaryStories` — Story Structure

`leadStory` is a single story object. `secondaryStories` is an array of the same structure.

```json
{
  "headline": "Bello Silences Bombers as Sox Walk Off in Ninth",
  "deck": "Boston starter strikes out ten; Devers delivers the decisive blow",
  "byline": "SportzBallz Staff",
  "body": "BOSTON — Brayan Bello held the Yankees to ...",
  "storyType": "game_recap",
  "factsUsed": ["gameId:716502", "leaders:ERA:Bello"]
}
```

| Field       | Type             | Description                                                     |
| ----------- | ---------------- | --------------------------------------------------------------- |
| `headline`  | string           | Story headline                                                  |
| `deck`      | string           | Subheadline / summary line                                      |
| `byline`    | string           | Attribution line                                                |
| `body`      | string           | Full story body text (may include HTML markup)                  |
| `storyType` | string           | See story type values below                                     |
| `factsUsed` | array of strings | Source fact references used to generate and validate this story |

### `storyType` values

`game_recap`, `game_preview`, `standings_update`, `trade_deadline`, `injury_update`, `milestone`, `special`

---

## `standings` — League Standings

```json
{
  "AL": {
    "East": [ ... ],
    "Central": [ ... ],
    "West": [ ... ],
    "WildCard": [ ... ]
  },
  "NL": {
    "East": [ ... ],
    "Central": [ ... ],
    "West": [ ... ],
    "WildCard": [ ... ]
  }
}
```

Each array contains `StandingsRow` objects:

```json
{
  "rank": 1,
  "team": "NYY",
  "teamFull": "New York Yankees",
  "wins": 55,
  "losses": 36,
  "pct": 0.604,
  "gb": 0.0,
  "wcgb": null,
  "streak": "W3",
  "last10": "7-3",
  "runsScored": 412,
  "runsAllowed": 338,
  "homeRecord": "28-17",
  "awayRecord": "27-19",
  "eliminationNumber": null
}
```

| Field               | Type          | Description                                       |
| ------------------- | ------------- | ------------------------------------------------- |
| `rank`              | int           | Standing position within division or wild card    |
| `team`              | string        | Team abbreviation                                 |
| `teamFull`          | string        | Full team name                                    |
| `wins`              | int           | Season wins                                       |
| `losses`            | int           | Season losses                                     |
| `pct`               | float         | Winning percentage                                |
| `gb`                | float         | Games behind division leader (0.0 = leader)       |
| `wcgb`              | float or null | Wild card games behind; null for division leaders |
| `streak`            | string        | Current win/loss streak (e.g. `W3`, `L1`)         |
| `last10`            | string        | Record over last 10 games                         |
| `runsScored`        | int           | Season runs scored                                |
| `runsAllowed`       | int           | Season runs allowed                               |
| `homeRecord`        | string        | Home record in `W-L` format                       |
| `awayRecord`        | string        | Away record in `W-L` format                       |
| `eliminationNumber` | int or null   | Magic number to eliminate; null if not applicable |

---

## `leagueLeaders` — Statistical Leaders

```json
{
  "batting": {
    "AVG": [ ... ],
    "HR": [ ... ],
    "RBI": [ ... ],
    "OPS": [ ... ],
    "SB": [ ... ]
  },
  "pitching": {
    "ERA": [ ... ],
    "SO": [ ... ],
    "W": [ ... ],
    "SV": [ ... ],
    "WHIP": [ ... ]
  }
}
```

Each category array contains `LeaderEntry` objects (top 5 per category by default):

```json
{
  "rank": 1,
  "player": "Aaron Judge",
  "team": "NYY",
  "position": "RF",
  "value": 0.321,
  "gamesPlayed": 89,
  "league": "AL",
  "qualified": true
}
```

| Field         | Type         | Description                                                          |
| ------------- | ------------ | -------------------------------------------------------------------- |
| `rank`        | int          | Rank within the category                                             |
| `player`      | string       | Player full name                                                     |
| `team`        | string       | Team abbreviation                                                    |
| `position`    | string       | Primary position                                                     |
| `value`       | float or int | Stat value (float for rate stats, int for counting stats)            |
| `gamesPlayed` | int          | Games played or appearances                                          |
| `league`      | string       | `AL` or `NL`                                                         |
| `qualified`   | bool         | Whether the player meets the plate appearance or innings requirement |

---

## `transactions` — Transaction Log

```json
[
  {
    "type": "trade",
    "team": "LAD",
    "player": "Marcus Semien",
    "effectiveDate": "2026-07-12",
    "explanation": "Acquired from Texas Rangers in exchange for two prospects.",
    "sourceTimestamp": "2026-07-12T18:44:00Z"
  }
]
```

| Field             | Type   | Description                                      |
| ----------------- | ------ | ------------------------------------------------ |
| `type`            | string | Transaction type (see below)                     |
| `team`            | string | Team abbreviation of the primary team            |
| `player`          | string | Player name                                      |
| `effectiveDate`   | string | Date the transaction takes effect (`YYYY-MM-DD`) |
| `explanation`     | string | Human-readable description of the transaction    |
| `sourceTimestamp` | string | ISO 8601 UTC timestamp from the source data      |

### Transaction `type` values

`trade`, `signing`, `extension`, `release`, `dfa`, `recall`, `option`, `activation`, `il_placement`, `il_return`, `retirement`

---

## `injuries` — Injury Report

```json
[
  {
    "player": "Spencer Strider",
    "team": "ATL",
    "injury": "right elbow UCL tear",
    "rosterStatus": "60-day IL",
    "dateOfInjury": "2026-04-10",
    "expectedReturn": "2026-09-01",
    "confidenceLevel": "low",
    "latestUpdate": "Strider threw a light bullpen session on July 11.",
    "updateTimestamp": "2026-07-12T14:00:00Z"
  }
]
```

| Field             | Type           | Description                                                       |
| ----------------- | -------------- | ----------------------------------------------------------------- |
| `player`          | string         | Player full name                                                  |
| `team`            | string         | Team abbreviation                                                 |
| `injury`          | string         | Injury description                                                |
| `rosterStatus`    | string         | Current roster status                                             |
| `dateOfInjury`    | string         | Date injured (`YYYY-MM-DD`)                                       |
| `expectedReturn`  | string or null | Estimated return date (`YYYY-MM-DD`); null if unknown             |
| `confidenceLevel` | string         | Confidence in return estimate: `high`, `medium`, `low`, `unknown` |
| `latestUpdate`    | string         | Most recent update text                                           |
| `updateTimestamp` | string         | ISO 8601 UTC timestamp of the latest update                       |

### `rosterStatus` values

`10-day IL`, `15-day IL`, `60-day IL`, `day-to-day`, `out for season`

---

## `generationMetadata` — Run Diagnostics

```json
{
  "runId": "a3f8c1d2",
  "phaseDurations": {
    "collect": 4.21,
    "normalize": 0.38,
    "generate": 11.84,
    "validate": 0.19,
    "render": 0.72,
    "publish": 0.55
  },
  "providerStatuses": {
    "mlbApi": "ok",
    "aiProvider": "ok"
  },
  "dataFreshness": {
    "liveScores": "2026-07-13T06:30:00Z",
    "standings": "2026-07-13T06:28:00Z",
    "leagueLeaders": "2026-07-13T06:28:00Z",
    "transactions": "2026-07-13T05:15:00Z",
    "injuries": "2026-07-12T20:00:00Z"
  }
}
```

| Field              | Type   | Description                                                     |
| ------------------ | ------ | --------------------------------------------------------------- |
| `runId`            | string | Short hex identifier shared across all log events for this run  |
| `phaseDurations`   | object | Wall-clock seconds for each pipeline stage                      |
| `providerStatuses` | object | `ok`, `degraded`, or `failed` per external provider             |
| `dataFreshness`    | object | ISO 8601 UTC timestamp of the most recent data for each section |

## ADDED Requirements

### Requirement: Edition Metadata
An Edition JSON document MUST include the following metadata fields: `id` (unique run identifier), `type` (edition type enum), `date` (publication date), `generatedAt` (ISO 8601 timestamp with timezone), `dataCurrentThrough` (ISO 8601 timestamp with timezone), `timezone` (IANA timezone string), and `status` (publication status).

#### Scenario: Edition metadata is present and complete
- **WHEN** an Edition JSON document is generated
- **THEN** all required metadata fields (`id`, `type`, `date`, `generatedAt`, `dataCurrentThrough`, `timezone`, `status`) MUST be present and non-null

#### Scenario: Edition metadata timestamps are ISO 8601 with timezone
- **WHEN** an Edition JSON document is generated
- **THEN** `generatedAt` and `dataCurrentThrough` MUST be ISO 8601 strings that include timezone offset or UTC designator

---

### Requirement: Edition Types and Content Emphasis
The `type` field MUST be one of: `morning`, `midday`, `evening`, `late`, `final`, `special`. Each edition type SHALL enforce the following content emphasis rules: `morning` emphasizes previous-day game recaps and overnight transactions; `midday` emphasizes live standings and upcoming game previews; `evening` emphasizes night-game previews and afternoon results; `late` emphasizes completed same-day games and standings updates; `final` emphasizes full-day summary with complete standings; `special` is reserved for breaking news or postseason editions.

#### Scenario: Morning edition emphasizes recaps
- **WHEN** edition type is `morning`
- **THEN** the content selection pipeline MUST prioritize previous-day game recaps as lead candidates and secondary stories

#### Scenario: Evening edition emphasizes previews
- **WHEN** edition type is `evening`
- **THEN** the content selection pipeline MUST prioritize upcoming night-game previews in secondary story slots

#### Scenario: Invalid edition type is rejected
- **WHEN** an Edition JSON document is constructed with a `type` value outside the allowed enum
- **THEN** schema validation MUST fail and reject the document

---

### Requirement: Lead Story Structure
An Edition JSON document MUST include a `leadStory` object containing: `headline` (string), `deck` (string), `byline` (string), `body` (array of paragraph strings), `primaryImage` (nullable image object with `url`, `altText`, `caption`, `credit`), `caption` (string), `sourceDataReferences` (array of reference objects linking to source facts), `storyType` (enum: `game_recap`, `preview`, `transaction`, `injury`, `milestone`, `analysis`), `teams` (array of team identifiers), and `players` (array of player identifiers).

#### Scenario: Lead story contains all required fields
- **WHEN** an Edition JSON document is generated
- **THEN** the `leadStory` object MUST contain all required fields with non-empty values for `headline`, `deck`, `byline`, and at least one `body` paragraph

#### Scenario: Lead story source references are traceable
- **WHEN** an Edition JSON document is generated
- **THEN** each entry in `leadStory.sourceDataReferences` MUST correspond to a verifiable fact within the same Edition JSON document

---

### Requirement: Secondary Stories
An Edition JSON document MUST include a `secondaryStories` array containing between 3 and 6 story objects. Each secondary story MUST conform to the same structure as the lead story.

#### Scenario: Secondary story count is within bounds
- **WHEN** an Edition JSON document is generated
- **THEN** `secondaryStories` MUST contain at least 3 and no more than 6 entries

#### Scenario: Secondary stories are structurally valid
- **WHEN** an Edition JSON document is generated
- **THEN** each entry in `secondaryStories` MUST include `headline`, `deck`, `byline`, `body`, `storyType`, `teams`, and `sourceDataReferences`

---

### Requirement: Game Record Structure
Each game record in the Edition JSON MUST include: `gameId`, `awayTeam` (team identifier + name), `homeTeam` (team identifier + name), `awayScore` (nullable integer), `homeScore` (nullable integer), `status` (game status enum), `currentInning` (nullable integer), `currentInningHalf` (nullable: `top` or `bottom`), `outs` (nullable integer 0–3), `currentPitcher` (nullable player reference), `startingPitchers` (object with `away` and `home` player references), `scheduledStartTime` (ISO 8601 with timezone), `ballpark` (venue name), `isDoubleheader` (boolean), `doubleheaderGame` (nullable integer 1 or 2), `postponementReason` (nullable string), and `recapLink` (nullable URL string).

#### Scenario: Final game record has scores
- **WHEN** a game record has `status` of `final`
- **THEN** `awayScore` and `homeScore` MUST be non-null integers

#### Scenario: Postponed game record includes reason
- **WHEN** a game record has `status` of `postponed`
- **THEN** `postponementReason` MUST be a non-null, non-empty string

#### Scenario: In-progress game record includes inning and outs
- **WHEN** a game record has `status` of `in_progress`
- **THEN** `currentInning`, `currentInningHalf`, and `outs` MUST all be non-null

---

### Requirement: Game Status Values
The `status` field on a game record MUST be one of: `final`, `in_progress`, `delayed`, `postponed`, `suspended`, `scheduled`.

#### Scenario: All game status values are from the allowed enum
- **WHEN** an Edition JSON document is validated
- **THEN** every game record's `status` field MUST match one of the six allowed values

#### Scenario: Unrecognized game status fails validation
- **WHEN** a game record contains a `status` value not in the allowed enum
- **THEN** schema validation MUST reject the document

---

### Requirement: Standings Row Structure
Each standings row MUST include: `team` (team identifier + name), `wins` (integer), `losses` (integer), `pct` (float, three decimal places), `gb` (float or `"-"` for division leader), `wcGb` (nullable float or `"-"`), `last10` (string in `"W-L"` format), `streak` (string, e.g., `"W3"` or `"L1"`), `homeRecord` (string in `"W-L"` format), `awayRecord` (string in `"W-L"` format), and `runDifferential` (signed integer).

#### Scenario: Division leader has GB of dash
- **WHEN** a standings row is for the division leader
- **THEN** the `gb` field MUST be `"-"`

#### Scenario: Wild-card standings include WC-GB
- **WHEN** standings rows are generated for the wild-card pool
- **THEN** `wcGb` MUST be non-null for all rows

---

### Requirement: League Leader Entry Structure
Each league leader entry MUST include: `rank` (integer starting at 1), `player` (player identifier + display name), `team` (team identifier + abbreviation), `position` (position string), `value` (numeric or string representation of the statistic), `gamesPlayed` (integer, or `inningsPitched` float for pitchers), `league` (enum: `AL` or `NL`), and `isQualified` (boolean indicating whether the player meets MLB qualification thresholds).

#### Scenario: League leader entries are ranked sequentially
- **WHEN** a league leader category list is generated
- **THEN** `rank` values MUST be sequential integers starting at 1 with no gaps

#### Scenario: Unqualified player is flagged
- **WHEN** a player does not meet the MLB qualification threshold for a category
- **THEN** `isQualified` MUST be `false` on their leader entry

---

### Requirement: Transaction Record Structure
Each transaction record MUST include: `type` (enum: `trade`, `dfa`, `signed`, `released`, `optioned`, `recalled`, `placed_on_il`, `activated`, `claimed`, `retired`, `other`), `team` (team identifier), `player` (player identifier + display name), `effectiveDate` (ISO 8601 date string), `explanation` (human-readable string), and `sourceTimestamp` (ISO 8601 timestamp of the source data point).

#### Scenario: Transaction record type is from allowed enum
- **WHEN** a transaction record is included in the Edition JSON
- **THEN** its `type` field MUST match one of the defined enum values

#### Scenario: Transaction record has effective date and explanation
- **WHEN** a transaction record is included in the Edition JSON
- **THEN** `effectiveDate` and `explanation` MUST be non-null and non-empty

---

### Requirement: Injury Record Structure
Each injury record MUST include: `player` (player identifier + display name), `team` (team identifier), `injury` (injury description string), `rosterStatus` (enum: `10-day IL`, `15-day IL`, `60-day IL`, `day-to-day`, `out`), `dateOfInjury` (ISO 8601 date string), `expectedReturn` (nullable ISO 8601 date string — MUST be null if not confirmed by source data), `confidenceLevel` (enum: `confirmed`, `estimated`, `unknown`), `latestUpdate` (string), and `updateTimestamp` (ISO 8601 timestamp).

#### Scenario: Injury record with unconfirmed return date uses null
- **WHEN** no source data confirms a player's expected return date
- **THEN** `expectedReturn` MUST be null

#### Scenario: Injury record roster status is from allowed enum
- **WHEN** an injury record is included in the Edition JSON
- **THEN** `rosterStatus` MUST match one of the defined enum values

---

### Requirement: Historical Item Structure
Each historical item in the `history` section MUST include: `date` (historical date string), `headline` (string), `body` (string), `category` (enum: `on_this_day`, `milestone_anniversary`, `record_reference`), and `relatedTeams` (array of team identifiers, may be empty).

#### Scenario: Historical item has required fields
- **WHEN** a historical item is included in the Edition JSON
- **THEN** `date`, `headline`, `body`, and `category` MUST all be non-null and non-empty

---

### Requirement: Data Freshness Metadata
The Edition JSON MUST include a `dataFreshness` object containing per-section timestamps indicating the most recent data point incorporated into each section. Sections MUST include at minimum: `scores`, `standings`, `leagueLeaders`, `transactions`, `injuries`, `schedule`.

#### Scenario: Data freshness timestamps are present for all sections
- **WHEN** an Edition JSON document is generated
- **THEN** `dataFreshness` MUST contain a non-null ISO 8601 timestamp for each required section

---

### Requirement: Generation Metadata
The Edition JSON MUST include a `generationMeta` object containing: `runId` (unique string), `providerStatuses` (map of provider name to status enum: `success`, `partial`, `failed`, `skipped`), and `phaseDurations` (map of phase name to duration in milliseconds).

#### Scenario: Generation metadata records all provider statuses
- **WHEN** an Edition JSON document is generated
- **THEN** `generationMeta.providerStatuses` MUST include an entry for every provider that was attempted during the run

#### Scenario: Generation metadata records phase durations
- **WHEN** an Edition JSON document is generated
- **THEN** `generationMeta.phaseDurations` MUST include entries for all executed phases

---

### Requirement: Schema Validation Before Publication
The Edition JSON MUST pass JSON Schema validation before it is used as input to the HTML renderer or the publishing pipeline. Any Edition JSON that fails schema validation MUST NOT be published.

#### Scenario: Valid Edition JSON passes schema validation
- **WHEN** a fully populated Edition JSON document is validated against the JSON Schema
- **THEN** validation MUST pass with no errors

#### Scenario: Invalid Edition JSON is rejected before publication
- **WHEN** an Edition JSON document is missing required fields or contains invalid enum values
- **THEN** schema validation MUST fail and the publishing pipeline MUST NOT proceed

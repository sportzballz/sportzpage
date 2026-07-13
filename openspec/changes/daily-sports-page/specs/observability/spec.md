## ADDED Requirements

### Requirement: Structured Generation Run Log Entry
Each generation run MUST produce a structured log entry containing all of the following fields: `runId`, `editionId`, `startTime`, `completionTime`, phase durations for each pipeline phase (`collection`, `normalization`, `generation`, `validation`, `rendering`, `publishing`), `providersUsed` (list of provider names), `providerFailures` (list of failed provider names), `gameCount`, `storyCount`, `leaderCategoryCount`, `validationResults` (summary of pass/fail per validation check), `publishedUrl`, and `finalStatus`.

#### Scenario: Successful run records all required fields
- **WHEN** a generation run completes successfully
- **THEN** the structured log entry MUST contain all required fields with non-null values for all fields applicable to a completed run

#### Scenario: Failed run records failure fields
- **WHEN** a generation run fails at any phase
- **THEN** the structured log entry MUST record `finalStatus` as `failed`, include the phase at which failure occurred, and include all fields that were populated before the failure

---

### Requirement: Run Status Lifecycle
Run status MUST transition through the following states in order: `started` → `collecting` → `normalizing` → `generating` → `validating` → `rendering` → `publishing` → `published`. A run that encounters an unrecoverable error at any stage MUST transition to `failed`. A run that publishes successfully but with some optional sections omitted due to provider failure MUST use the terminal status `published_degraded`.

#### Scenario: Successful run reaches published status
- **WHEN** all pipeline stages complete without error
- **THEN** the final run status MUST be `published`

#### Scenario: Run failure recorded with correct terminal status
- **WHEN** an unrecoverable error occurs during any pipeline phase
- **THEN** the run status MUST be set to `failed` and MUST NOT advance to any subsequent status

---

### Requirement: published_degraded Status
The `published_degraded` status MUST be used when a run publishes scores, standings, and schedule data successfully but one or more optional sections (such as AI-generated stories or league leaders from a failed provider) were omitted. A `published_degraded` run MUST still trigger a non-critical alert.

#### Scenario: published_degraded when AI fails but scores publish
- **WHEN** the AI provider is unavailable and fallback templates are used, but all data sections publish successfully
- **THEN** the run status MUST be `published_degraded` and a non-critical alert MUST be sent to the configured channel

---

### Requirement: Structured JSON-Serializable Logs
All log output from the generation pipeline MUST be structured and JSON-serializable. Log entries MUST NOT use unstructured free-text formats as the primary log output. Each log entry MUST include at minimum: `timestamp`, `level`, `runId`, `phase`, and `message`.

#### Scenario: Log entries are JSON-serializable
- **WHEN** any pipeline phase produces a log entry
- **THEN** the entry MUST be serializable to valid JSON with no non-serializable objects

---

### Requirement: Alert on Failed Run
A failed generation run MUST trigger an alert to the configured alert channel. The alert MUST include: `runId`, `editionId`, the phase at which the failure occurred, and a summary of the error.

#### Scenario: Failed render triggers alert
- **WHEN** the rendering phase fails
- **THEN** the configured alert channel MUST receive an alert containing the `runId`, `editionId`, phase name (`rendering`), and error summary

---

### Requirement: Last Known Good Edition Tracking
The system MUST track the last known good edition by storing its output path, edition ID, and publication timestamp in a persistent location. This record MUST be updated only on a successful `published` or `published_degraded` run.

#### Scenario: Last known good updated on successful publication
- **WHEN** a run reaches `published` or `published_degraded` status
- **THEN** the last known good record MUST be updated with the new edition's path, edition ID, and publication timestamp

#### Scenario: Last known good not updated on failed run
- **WHEN** a run terminates with `failed` status
- **THEN** the last known good record MUST NOT be modified

---

### Requirement: Alertable Metrics
Generation run metrics MUST be structured in a way that supports automated alerting thresholds. At minimum, the following metrics MUST be recorded and suitable for threshold-based alerting: total run duration, phase durations, provider failure count, validation failure count, and story count.

#### Scenario: Run duration metric recorded and alertable
- **WHEN** a generation run completes
- **THEN** the total run duration MUST be recorded as a numeric value suitable for comparison against a configured alerting threshold

---

### Requirement: Edition Health Report
The system MUST produce an edition health report for each published edition summarizing data freshness per section. The report MUST indicate, for each section, whether the data is current, stale, or unavailable, based on the `dataFreshness` timestamps in the Edition JSON.

#### Scenario: Freshness report shows stale sections
- **WHEN** an edition health report is generated and one or more sections have a `dataFreshness` timestamp older than the configured staleness threshold
- **THEN** the report MUST identify those sections as stale with their last-updated timestamp

#### Scenario: Freshness report shows unavailable sections
- **WHEN** a section's data was not available during collection and the section was omitted from the Edition JSON
- **THEN** the edition health report MUST mark that section as `unavailable`

## ADDED Requirements

### Requirement: Configurable Generation Schedule
The generation schedule MUST be defined in `config/schedules.yaml`. Schedule times, edition types, and timezone MUST NOT be hardcoded in application source code. Changes to the schedule MUST take effect on the next scheduler evaluation without code changes.

#### Scenario: Schedule loaded from config file
- **WHEN** the scheduler initializes
- **THEN** it MUST load all schedule entries from `config/schedules.yaml` and MUST NOT use any hardcoded time values

---

### Requirement: Default Schedule
The default schedule MUST define the following generation runs in the `America/New_York` timezone unless overridden in configuration: 06:00 Morning edition, 12:00 Midday edition, 17:00 Evening edition, 23:30 Late edition.

#### Scenario: Morning edition triggered at 06:00 Eastern
- **WHEN** the scheduler evaluates at 06:00 America/New_York
- **THEN** a Morning edition generation run MUST be triggered

#### Scenario: All four default schedule entries produce runs
- **WHEN** the default schedule is active and each scheduled time is reached
- **THEN** a generation run MUST be triggered for the corresponding edition type at each of the four default times

---

### Requirement: Manual Trigger
The system MUST support manual trigger of a generation run. A manual trigger MUST accept an optional edition type override. A manually triggered run MUST follow the same pipeline as a scheduled run.

#### Scenario: Manual trigger initiates a full generation run
- **WHEN** the manual trigger command is invoked
- **THEN** a complete generation run MUST execute through all pipeline stages and result in a published or failed edition

---

### Requirement: Event-Triggered Runs
The system MUST support event-triggered generation runs for the following events: post-game completion (when the last scheduled game of the day ends), post-significant-transaction (when a trade or major transaction is detected), and pre-first-game (a preview edition generated before the first game of the day starts).

#### Scenario: Event trigger fires after game completion
- **WHEN** the system detects that the last scheduled game of the day has reached `final` status
- **THEN** an event-triggered generation run MUST be initiated

#### Scenario: Pre-first-game trigger fires before first game
- **WHEN** the system detects that the first scheduled game of the day is within the configured pre-game window
- **THEN** a pre-first-game event-triggered run MUST be initiated

---

### Requirement: Edition Type Assignment
The edition type assigned to a generation run MUST be determined based on the generation time and the available data at that time. The assignment rules MUST be defined in `config/schedules.yaml` and MUST map time windows and data conditions to edition types (`morning`, `midday`, `evening`, `late`, `final`, `special`).

#### Scenario: Edition type assigned based on generation time
- **WHEN** a scheduled run triggers at 06:00
- **THEN** the run MUST be assigned edition type `morning`

#### Scenario: Post-game event run assigned late or final type
- **WHEN** an event-triggered run fires after all games are complete for the day
- **THEN** the run MUST be assigned edition type `final` or `late` as defined by the schedule configuration

---

### Requirement: Edition Type Content Influence
Each edition type MUST influence the content selection behavior of the editorial pipeline: `morning` MUST emphasize previous-day game recaps; `midday` MUST emphasize live standings and upcoming game previews; `evening` MUST emphasize night-game previews and afternoon results; `late` MUST emphasize completed same-day games and standings updates; `final` MUST produce a full-day summary with complete standings; `special` MUST be reserved for breaking news or postseason content.

#### Scenario: Morning edition content emphasizes previous-day recaps
- **WHEN** a run is assigned edition type `morning`
- **THEN** the editorial pipeline MUST prioritize previous-day game recaps in lead and secondary story candidates

---

### Requirement: Concurrent Run Prevention
The scheduler MUST NOT allow concurrent generation runs targeting the same output destination. If a run is already in progress when a new trigger fires for the same target, the new trigger MUST be deferred or skipped, and a warning MUST be logged.

#### Scenario: Concurrent run prevention for same target
- **WHEN** a second trigger fires while a generation run for the same target is already in progress
- **THEN** the scheduler MUST NOT start a second concurrent run and MUST log a warning with the run ID of the in-progress run

---

### Requirement: Stale Edition Warning
If no successful publication occurs within the expected window for a given target, the live page MUST display a stale-data warning banner showing the timestamp of the last successfully published edition.

#### Scenario: Stale edition warning displayed when publication is overdue
- **WHEN** the current time exceeds the expected publication window and no successful run has completed
- **THEN** the live page MUST display a clearly labeled stale-data warning including the `generatedAt` timestamp of the last published edition

---

### Requirement: Run Isolation
Each generation run MUST be isolated. A failed run MUST NOT leave partial state in the build directory, the live output directory, or the run-state tracking store. On failure, all partial artifacts MUST be cleaned up.

#### Scenario: Failed run leaves no partial state
- **WHEN** a generation run fails at any pipeline stage
- **THEN** no partial build artifacts MUST remain in the live output directory, and the run state MUST be recorded as `failed` with a cleanup confirmation

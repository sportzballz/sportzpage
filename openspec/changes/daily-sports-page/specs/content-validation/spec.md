## ADDED Requirements

### Requirement: Score Validation Against Edition JSON
The validator MUST confirm that every score mentioned in editorial content matches the corresponding game record in the Edition JSON. A mismatch MUST cause validation to fail.

#### Scenario: Score validation pass
- **WHEN** editorial content references a final score that matches the Edition JSON game record
- **THEN** score validation MUST pass for that story

#### Scenario: Score mismatch triggers rejection
- **WHEN** editorial content references a score that differs from the Edition JSON game record
- **THEN** the validator MUST reject the story and record a structured validation error identifying the mismatched game ID and score values

---

### Requirement: Player-Team Relationship Validation
The validator MUST confirm that all player-team relationships cited in editorial content are accurate according to the Edition JSON roster and transaction data. A player cited as a member of a team they do not belong to MUST cause validation to fail.

#### Scenario: Valid player-team relationship passes validation
- **WHEN** editorial content cites a player as belonging to a team and the Edition JSON confirms that relationship
- **THEN** validation MUST pass for that reference

#### Scenario: Incorrect player-team relationship causes rejection
- **WHEN** editorial content cites a player as belonging to a team not reflected in the Edition JSON
- **THEN** the validator MUST reject the story and record a structured validation error

---

### Requirement: Statistic Value Validation
The validator MUST confirm that all statistic values cited in editorial content match the corresponding values in the Edition JSON league leader, game record, or player data. A statistic that does not match MUST cause validation to fail.

#### Scenario: Correct statistic passes validation
- **WHEN** editorial content cites a player statistic that matches the Edition JSON
- **THEN** validation MUST pass for that statistic reference

#### Scenario: Incorrect statistic causes rejection
- **WHEN** editorial content cites a statistic value that does not match the Edition JSON
- **THEN** the validator MUST reject the story with a structured error identifying the statistic and the discrepancy

---

### Requirement: Unsupported Claim Detection
The validator MUST detect claims in editorial content that are not traceable to the `factsUsed` references attached to the story. Any assertion not backed by a `factsUsed` reference MUST be flagged as an unsupported claim and cause validation to fail.

#### Scenario: Unsupported claim detected
- **WHEN** editorial content includes an assertion about a player performance, transaction, or standings implication that does not appear in the story's `factsUsed` references
- **THEN** the validator MUST flag it as an unsupported claim and reject the story

---

### Requirement: Duplicate Text Detection
The validator MUST detect duplicate or substantially repeated text across stories within the same edition. Duplicate text MUST cause validation to fail for the affected stories.

#### Scenario: Duplicate text detected across two stories
- **WHEN** two stories in the same edition share substantially identical paragraph text
- **THEN** the validator MUST flag the duplicate and reject both stories until the duplication is resolved

---

### Requirement: Malformed Content Rejection
The validator MUST reject any content that is missing required fields or contains empty required sections. Required fields include at minimum: `headline`, `deck`, `byline`, `body`, `storyType`, `teams`, and `sourceDataReferences`.

#### Scenario: Empty headline rejected
- **WHEN** a story object has an empty string or null `headline`
- **THEN** the validator MUST reject the story with a structured error identifying the missing field

#### Scenario: Missing body section rejected
- **WHEN** a story object has a null or empty `body` array
- **THEN** the validator MUST reject the story

---

### Requirement: Failed Validation Blocks Publication and Triggers Alert
Any validation failure MUST prevent the affected content from being published. The system MUST trigger a configured alert when a validation failure occurs.

#### Scenario: Validation failure blocks publication
- **WHEN** any story fails validation
- **THEN** the publishing pipeline MUST NOT publish an edition that includes the failed story, and the run status MUST be set to `failed` or `published_degraded` depending on whether fallback content is available

#### Scenario: Validation failure triggers alert
- **WHEN** a validation failure occurs during a generation run
- **THEN** the configured alert channel MUST receive a notification containing the run ID, edition ID, and a summary of the validation errors

---

### Requirement: factsUsed Reference Validation
The validator MUST check each story's `factsUsed` array against the Edition JSON to confirm that every cited reference resolves to an actual data point in the edition. Unresolvable references MUST cause validation to fail.

#### Scenario: Valid factsUsed references pass validation
- **WHEN** all entries in a story's `factsUsed` array resolve to data points present in the Edition JSON
- **THEN** reference validation MUST pass

#### Scenario: Unresolvable factsUsed reference causes rejection
- **WHEN** a `factsUsed` entry references a game ID, player ID, or statistic not present in the Edition JSON
- **THEN** the validator MUST reject the story with a structured error

---

### Requirement: Injury Return Date Validation
The validator MUST reject any editorial content that states or implies a specific injury return date that is not present in the Edition JSON injury records. The system MUST NOT invent a return date when none exists in source data.

#### Scenario: Injury return date from source data passes validation
- **WHEN** editorial content cites an injury return date that matches the `expectedReturn` field in the Edition JSON injury record
- **THEN** validation MUST pass for that reference

#### Scenario: Invented injury return date rejected
- **WHEN** AI-generated content includes a specific injury return date and the corresponding Edition JSON injury record has `expectedReturn` set to null
- **THEN** the validator MUST reject the story with a structured error identifying the unsupported return date claim

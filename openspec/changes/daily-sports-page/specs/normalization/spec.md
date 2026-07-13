## ADDED Requirements

### Requirement: Provider-Specific Response Conversion
The normalizer MUST convert provider-specific raw responses into the system's internal Pydantic models. Each supported provider MUST have a dedicated normalizer module that handles that provider's schema.

#### Scenario: Single-provider normalization produces internal model
- **WHEN** the normalizer receives a raw response from a single provider
- **THEN** it MUST produce a populated internal Pydantic model with all required fields mapped and no provider-specific field names present in the output

---

### Requirement: Canonical Team ID Standardization
All team identifiers in normalized output MUST use canonical internal team IDs. Provider-specific team identifiers MUST NOT appear in any internal Pydantic model.

#### Scenario: Provider team ID is replaced with canonical ID
- **WHEN** the normalizer processes a raw response containing a provider-specific team identifier
- **THEN** the resulting internal model MUST contain only the canonical internal team ID

---

### Requirement: Canonical Player ID Standardization
All player identifiers in normalized output MUST use canonical internal player IDs. Provider-specific player identifiers MUST NOT appear in any internal Pydantic model.

#### Scenario: Provider player ID is replaced with canonical ID
- **WHEN** the normalizer processes a raw response containing a provider-specific player identifier
- **THEN** the resulting internal model MUST contain only the canonical internal player ID

---

### Requirement: Game Status Mapping
Provider-specific game status strings MUST be mapped to the canonical game status enum (`final`, `in_progress`, `delayed`, `postponed`, `suspended`, `scheduled`). Unmappable status values MUST cause a normalization error.

#### Scenario: Game status mapped to canonical enum value
- **WHEN** the normalizer encounters a provider-specific game status string
- **THEN** the resulting game record MUST use the corresponding canonical status enum value

#### Scenario: Unmappable game status causes normalization error
- **WHEN** the normalizer encounters a provider game status string with no defined mapping
- **THEN** the normalizer MUST raise a structured normalization error and MUST NOT silently discard or default the value

---

### Requirement: ISO 8601 Datetime Normalization
All date and time values in normalized output MUST be expressed as ISO 8601 strings that include timezone information. Provider-supplied timestamps in other formats MUST be converted.

#### Scenario: Timezone normalization converts provider timestamp
- **WHEN** the normalizer receives a timestamp that lacks timezone information or uses a non-ISO format
- **THEN** the normalized output MUST contain an ISO 8601 string with explicit timezone offset or UTC designator

---

### Requirement: Cross-Provider Deduplication
When the same logical entity (game, player, team) is present in responses from multiple providers, the normalizer MUST deduplicate by canonical ID, producing a single record.

#### Scenario: Cross-provider deduplication produces one game record
- **WHEN** the normalizer receives game data for the same `gameId` from two different providers
- **THEN** the normalized output MUST contain exactly one game record for that `gameId`

---

### Requirement: Conflicting Data Reconciliation
When multiple providers supply conflicting values for the same field on the same entity, the normalizer MUST reconcile the conflict using configurable provider priority rules. The reconciliation decision and the losing value MUST be logged at debug level.

#### Scenario: Conflicting scores reconciled by priority rules
- **WHEN** two providers report different final scores for the same game
- **THEN** the normalizer MUST select the value from the higher-priority provider as defined in the provider priority configuration and log the discarded value

---

### Requirement: Normalizer Does Not Generate HTML
The normalizer MUST NOT produce HTML output of any kind. Its output MUST be limited to internal Pydantic model instances.

#### Scenario: Normalizer output contains no HTML
- **WHEN** normalization completes for any input
- **THEN** the output MUST be Pydantic model instances with no HTML content

---

### Requirement: Normalizer Does Not Make HTTP Requests
The normalizer MUST NOT make HTTP requests. All data MUST arrive as input from the collection stage. If additional data is required, it MUST be requested by the collection stage before normalization begins.

#### Scenario: Normalizer runs without network access
- **WHEN** normalization is executed in an environment with no network access
- **THEN** it MUST complete successfully using only its input data

---

### Requirement: Normalized Output Conforms to Internal Pydantic Schemas
The output of normalization MUST conform to the internal Pydantic model schemas. Any output that fails Pydantic model validation MUST be rejected before being passed to the statistics or editorial stages.

#### Scenario: Valid normalized output passes Pydantic validation
- **WHEN** the normalizer produces output from a well-formed provider response
- **THEN** the resulting Pydantic models MUST pass model-level validation with no validation errors

#### Scenario: Invalid normalized output is rejected
- **WHEN** normalization produces a model instance that fails Pydantic validation
- **THEN** the normalizer MUST raise a structured error and MUST NOT pass the invalid model to downstream stages

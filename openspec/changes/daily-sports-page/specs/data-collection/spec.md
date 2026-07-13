## ADDED Requirements

### Requirement: HTTP Data Retrieval
Collectors MUST retrieve raw data from MLB data providers via HTTP requests. Collectors MUST NOT embed provider responses directly in source code.

#### Scenario: Successful data collection from provider
- **WHEN** a collector makes an HTTP request to a configured MLB data provider endpoint
- **THEN** the raw response body MUST be saved to the cache directory with an accompanying provider timestamp

---

### Requirement: Authentication via Environment Variables
Collectors MUST handle authentication credentials exclusively via environment variables. Credentials MUST NOT be committed to version-controlled files, hardcoded in source code, or stored in configuration files that are not excluded from version control.

#### Scenario: API key loaded from environment variable
- **WHEN** a collector initializes and an API key is required
- **THEN** the key MUST be read from the configured environment variable name and MUST NOT appear in any committed source file or log output

---

### Requirement: Exponential Backoff Retry on Transient Failures
Collectors MUST implement exponential backoff retry logic for transient HTTP failures (e.g., 429, 500, 502, 503, 504 responses and connection timeouts). Maximum retries, initial delay, and maximum delay MUST each be independently configurable per provider.

#### Scenario: Provider timeout triggers retry with backoff
- **WHEN** a collector receives a connection timeout on the first attempt
- **THEN** the collector MUST retry up to the configured maximum retry count, with each retry delay no less than double the previous delay, not exceeding the configured maximum delay

#### Scenario: Non-transient error does not retry
- **WHEN** a collector receives an HTTP 401 or 403 response
- **THEN** the collector MUST NOT retry and MUST immediately record an authentication failure

---

### Requirement: Raw Response Cache
Collectors MUST save each raw provider response to a configurable cache directory. Each cache entry MUST include the provider's response timestamp so that staleness can be evaluated independently of the local write time.

#### Scenario: Raw response saved with provider timestamp
- **WHEN** a collector successfully receives a provider response
- **THEN** the cache entry MUST record the provider's own reported timestamp (from response headers or response body) alongside the raw payload

---

### Requirement: Stale Cache Rejection
Cache entries whose age exceeds a configurable maximum age MUST NOT be used as a fallback data source. The maximum age MUST be configurable per provider and per data type.

#### Scenario: Cache entry beyond max age is not used
- **WHEN** a collector fails to reach a provider and the most recent cache entry for that provider exceeds the configured maximum age
- **THEN** the collector MUST NOT return the stale cache entry as valid data and MUST record a data-unavailable failure

---

### Requirement: Provider Attribution
Collectors MUST record which providers contributed data to a given edition. This attribution MUST be included in the Edition JSON `generationMeta.providerStatuses` field.

#### Scenario: Provider attribution recorded in generation metadata
- **WHEN** a collection run completes
- **THEN** `generationMeta.providerStatuses` MUST contain an entry for every provider that was attempted, with status `success`, `partial`, `failed`, or `skipped`

---

### Requirement: Canonical Team ID Mapping
All team identifiers received from external providers MUST be mapped to canonical internal team IDs before being passed to the normalization stage. The mapping MUST be maintained in a versioned configuration file.

#### Scenario: Provider team ID mapped to canonical ID
- **WHEN** a collector receives data containing a provider-specific team identifier
- **THEN** the collector MUST resolve it to the canonical internal team ID using the configured mapping before saving or forwarding the data

---

### Requirement: Canonical Player ID Mapping
All player identifiers received from external providers MUST be mapped to canonical internal player IDs before being passed to the normalization stage.

#### Scenario: Provider player ID mapped to canonical ID
- **WHEN** a collector receives data containing a provider-specific player identifier
- **THEN** the collector MUST resolve it to the canonical internal player ID using the configured mapping

---

### Requirement: Collectors Do Not Generate HTML or Apply Business Logic
Collectors MUST NOT generate HTML output. Collectors MUST NOT apply editorial business logic, statistical calculations, or story selection. Their sole responsibility is raw data retrieval, caching, and ID mapping.

#### Scenario: Collector output contains no HTML
- **WHEN** a collector saves its output
- **THEN** the output MUST be raw provider data (JSON, XML, or equivalent) with no HTML tags or editorial transformations

---

### Requirement: Collection Completes Before Normalization
Data collection MUST fully complete — or fall back to valid cached data — before the normalization stage begins. The normalization stage MUST NOT start if collection has not produced a usable dataset.

#### Scenario: Normalization blocked until collection completes
- **WHEN** the data collection phase is still in progress
- **THEN** the normalization phase MUST NOT begin

#### Scenario: Provider unavailable with valid cached fallback
- **WHEN** a provider is unreachable and a cache entry exists within the configured maximum age
- **THEN** the collector MUST use the cached response, record the provider status as `partial`, and allow the pipeline to proceed

#### Scenario: Provider unavailable with no cache — fail gracefully
- **WHEN** a provider is unreachable and no valid cache entry exists
- **THEN** the collector MUST record the provider status as `failed`, log a structured error, and signal to the pipeline that the section dependent on that provider is unavailable

---

### Requirement: Fixture Generation Mode
The system MUST support a fixture generation mode that saves raw provider responses as test fixtures. Fixture generation MUST be triggerable without publishing an edition.

#### Scenario: Fixture generation mode saves raw responses
- **WHEN** the system is run with fixture generation mode enabled
- **THEN** each raw provider response MUST be saved to the configured fixture directory with a filename that includes the provider name and a timestamp

#### Scenario: Fixture generation does not publish
- **WHEN** the system is run with fixture generation mode enabled
- **THEN** no HTML rendering, validation, or publication steps MUST execute

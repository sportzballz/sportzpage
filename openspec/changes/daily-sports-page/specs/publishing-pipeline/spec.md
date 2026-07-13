## ADDED Requirements

### Requirement: Temporary Build Directory
The publisher MUST generate all output — HTML, static assets, and accompanying JSON files — into a temporary build directory before any file is written to the public output location. No partial output MUST be written directly to the live directory.

#### Scenario: Build output staged in temporary directory
- **WHEN** the publisher begins a publication run
- **THEN** all generated files MUST be written to a temporary build directory and MUST NOT appear at the public output path until the validation and atomic rename steps complete

---

### Requirement: Pre-Publication File Validation
The publisher MUST validate all required files are present in the build directory before proceeding with publication. Required files MUST include at minimum: `index.html`, all referenced static assets, and the Edition JSON.

#### Scenario: Failed validation blocks publication
- **WHEN** a required file is missing from the build directory
- **THEN** the publisher MUST abort publication, record a failure status, and MUST NOT modify the live output directory

---

### Requirement: HTML Syntax Check
The publisher MUST check the HTML syntax of `index.html` before publication. A document with invalid HTML MUST NOT be published.

#### Scenario: Invalid HTML syntax blocks publication
- **WHEN** the HTML syntax check detects malformed HTML in the build output
- **THEN** the publisher MUST abort publication and record the syntax errors in the run log

---

### Requirement: Internal Link and Asset Reference Check
The publisher MUST verify that all internal links and asset references (CSS, JS, images, fonts) within the HTML output resolve to files present in the build directory. Broken references MUST block publication.

#### Scenario: Broken asset reference blocks publication
- **WHEN** the HTML output references a static asset that is not present in the build directory
- **THEN** the publisher MUST abort publication and log the unresolved reference

---

### Requirement: Required Section ID Confirmation
The publisher MUST confirm that all required section IDs (`front-page`, `scoreboard`, `todays-games`, `standings`, `league-leaders`, `game-recaps`, `around-the-league`, `transactions`, `injuries`, `history`) are present in the HTML output before publication.

#### Scenario: Missing section ID blocks publication
- **WHEN** the HTML output is missing one or more required section IDs
- **THEN** the publisher MUST abort publication and record which section IDs were absent

---

### Requirement: Publication Timestamp Confirmation
The publisher MUST confirm that a publication timestamp is present in the HTML output before proceeding. An HTML file with no publication timestamp MUST NOT be published.

#### Scenario: Missing publication timestamp blocks publication
- **WHEN** the HTML output does not contain a publication timestamp element
- **THEN** the publisher MUST abort publication

---

### Requirement: Assets Published Before index.html
Static assets (CSS, JS, images, fonts) MUST be uploaded or copied to the output destination before `index.html` is written or renamed into place. This ensures no user receives an `index.html` that references assets not yet available.

#### Scenario: Asset upload precedes HTML publication
- **WHEN** the publisher executes a full publication
- **THEN** all static assets MUST be confirmed present at their destination paths before `index.html` is published

---

### Requirement: Atomic index.html Publication
Publication of `index.html` MUST be atomic, using a filesystem rename operation or equivalent mechanism. Partial writes MUST NOT be visible to readers.

#### Scenario: Atomic rename of index.html
- **WHEN** the publisher writes `index.html` to the public output location
- **THEN** it MUST use a write-to-temp-then-rename pattern so that the live file transitions from the previous edition to the new edition without an intermediate invalid state

---

### Requirement: Post-Publication URL Verification
The publisher MUST verify that the public URL for the edition returns a successful HTTP response after publication completes. A non-successful response MUST trigger a publication failure alert.

#### Scenario: Public URL returns success after publication
- **WHEN** publication completes
- **THEN** the publisher MUST make an HTTP GET request to the public URL and MUST confirm a 200-class response

#### Scenario: Non-successful response triggers alert
- **WHEN** the post-publication URL check returns a non-200 response
- **THEN** the publisher MUST record a failure, trigger the configured alert, and initiate rollback to the last known good edition

---

### Requirement: Publication Status Recording
The publisher MUST record the success or failure status of each publication attempt in the run log. Status MUST include the edition ID, output path, publication timestamp, and any errors encountered.

#### Scenario: Successful publication recorded in run log
- **WHEN** a publication completes successfully
- **THEN** the run log MUST contain a structured entry with edition ID, output path, and publication timestamp

---

### Requirement: CDN Cache Purge
When CDN purge is configured, the publisher MUST trigger a CDN cache purge for the affected URLs after a successful publication.

#### Scenario: CDN purge hook called after publication
- **WHEN** CDN purge is configured and publication succeeds
- **THEN** the publisher MUST call the configured CDN purge endpoint or CLI hook for the published URLs

---

### Requirement: Last Known Good Edition Preservation
The publisher MUST retain a reference to the last successfully published edition (path, edition ID, and timestamp) before overwriting it with a new edition. This reference MUST be used by the rollback mechanism.

#### Scenario: Last known good preserved before new publication
- **WHEN** the publisher is about to replace the live `index.html` with a new edition
- **THEN** it MUST record the current live edition's path and edition ID as the last known good before the rename

---

### Requirement: Failed Publication Does Not Replace Live Edition
A failed publication run MUST NOT modify the live edition. If the publisher aborts at any pre-publication validation step or if post-publication verification fails, the previously live edition MUST remain accessible.

#### Scenario: Failed validation leaves live edition unchanged
- **WHEN** publication is aborted due to a pre-publication validation failure
- **THEN** the current live `index.html` MUST remain unchanged and accessible

---

### Requirement: Rollback to Last Known Good
The publisher MUST support a rollback command that restores the last known good edition as the live `index.html`. Rollback MUST be atomic.

#### Scenario: Rollback to last known good edition
- **WHEN** the rollback command is executed
- **THEN** the last known good edition MUST be atomically renamed to the live `index.html` path

---

### Requirement: Archive Support
Archive creation is OPTIONAL for MVP but MUST be architecturally supported. Archive filenames MUST follow the pattern `/daily-sports-page/archive/YYYY-MM-DD-HHMM.html`.

#### Scenario: Archive file created at correct path
- **WHEN** archive creation is enabled and a publication succeeds
- **THEN** a copy of the published HTML MUST be written to a path matching `/daily-sports-page/archive/YYYY-MM-DD-HHMM.html` where the date and time reflect the edition's publication time

---

### Requirement: Cache-Control Headers
`index.html` MUST be served with `Cache-Control: public, max-age=60, must-revalidate`. Versioned static assets MUST be served with `Cache-Control: public, max-age=31536000, immutable`.

#### Scenario: index.html cache header is short-lived
- **WHEN** `index.html` is configured for serving
- **THEN** its `Cache-Control` header MUST be `public, max-age=60, must-revalidate`

#### Scenario: Versioned static asset cache header is long-lived
- **WHEN** a versioned static asset (CSS, JS) is configured for serving
- **THEN** its `Cache-Control` header MUST be `public, max-age=31536000, immutable`

---

### Requirement: Staging and Production Configuration Targets
The publisher MUST support separate configuration targets for staging and production environments. Output paths, CDN endpoints, and public URLs MUST be independently configurable per target.

#### Scenario: Staging publication uses staging configuration
- **WHEN** the publisher is invoked with the staging target
- **THEN** it MUST write output to the staging output path and use the staging CDN and URL configuration

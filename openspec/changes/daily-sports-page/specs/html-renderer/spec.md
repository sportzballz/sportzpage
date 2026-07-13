## ADDED Requirements

### Requirement: Edition JSON as Sole Rendering Input
The renderer MUST consume Edition JSON as its only data input and produce valid HTML5 output. The renderer MUST NOT query databases, make HTTP requests, or read any file other than the Edition JSON, template files, and static assets during rendering.

#### Scenario: Edition JSON renders all required sections
- **WHEN** a valid Edition JSON document is passed to the renderer
- **THEN** the output MUST be a valid HTML5 document containing all required section IDs

---

### Requirement: No Business Logic in Renderer
The renderer MUST NOT contain business logic for story selection, statistical calculation, standings derivation, or editorial scoring. All such decisions MUST be reflected in the Edition JSON before rendering begins.

#### Scenario: Renderer produces consistent output from identical input
- **WHEN** the same Edition JSON document is rendered twice
- **THEN** the HTML output MUST be byte-for-byte identical both times

---

### Requirement: HTML Escaping
All text content sourced from Edition JSON MUST be HTML-escaped by the Jinja2 template engine before insertion into the HTML output. Auto-escaping MUST be enabled globally; explicit `| safe` filters MUST NOT be used on user-derived or AI-generated text fields.

#### Scenario: HTML escaping prevents XSS
- **WHEN** an Edition JSON field contains characters such as `<`, `>`, `"`, `&`, or `'`
- **THEN** the rendered HTML MUST contain the corresponding HTML entities and MUST NOT render the characters as HTML markup

---

### Requirement: Required Section IDs
The rendered page MUST contain all of the following HTML section anchor IDs: `front-page`, `scoreboard`, `todays-games`, `standings`, `league-leaders`, `game-recaps`, `around-the-league`, `transactions`, `injuries`, `history`. Each ID MUST appear exactly once per page.

#### Scenario: All required section IDs are present
- **WHEN** an Edition JSON document is rendered
- **THEN** the HTML output MUST contain all ten required section IDs as element `id` attributes

#### Scenario: Section IDs are stable across editions
- **WHEN** two different Edition JSON documents are rendered
- **THEN** all required section IDs MUST be identical in both outputs

---

### Requirement: Masthead Content
The masthead MUST include the following as separate, individually addressable elements: publication name, edition type, publication date, generation timestamp (`generatedAt`), data cutoff timestamp (`dataCurrentThrough`), and timezone. Generation timestamp and data cutoff timestamp MUST be rendered in separate elements and MUST NOT be merged into a single string.

#### Scenario: Masthead shows generation timestamp and data cutoff separately
- **WHEN** an Edition JSON is rendered
- **THEN** the masthead MUST display `generatedAt` and `dataCurrentThrough` as distinct labeled elements

---

### Requirement: Scoreboard Grouping by Status
The scoreboard MUST display games grouped by status in the following order: in-progress, final, delayed, suspended, postponed, scheduled. Each group MUST be visually distinguished. The layout MUST use a compact newspaper-style format.

#### Scenario: Games grouped by status in scoreboard
- **WHEN** Edition JSON contains games with mixed statuses
- **THEN** the rendered scoreboard MUST group them by status in the specified order

---

### Requirement: League Leaders Embedded Without API Call
All league leader category data MUST be embedded in the static HTML page or in accompanying static JSON files that are co-deployed with the page. Switching between leader categories MUST NOT require any live API call at page-load or interaction time.

#### Scenario: League leaders embedded without API call
- **WHEN** a user switches between league leader categories with JavaScript enabled
- **THEN** no network request to a live API MUST be made; data MUST be read from the embedded page data or co-deployed static JSON

---

### Requirement: Core Content Readable Without JavaScript
The following content MUST be fully readable when JavaScript is disabled: headline, lead story, scores, schedule, standings, league leaders, game recaps, transactions, injuries, and publication timestamp.

#### Scenario: Core content visible with JavaScript disabled
- **WHEN** the rendered page is loaded in a browser with JavaScript disabled
- **THEN** all core content sections MUST be visible and readable without any JavaScript execution

---

### Requirement: JavaScript Enhancement Scope
JavaScript MAY be used exclusively for: league-leader category switching, section collapsing, print controls, theme switching, page navigation, and copy-link buttons. JavaScript MUST NOT be required for any core content to be readable.

#### Scenario: JavaScript enhancements do not hide core content
- **WHEN** JavaScript is disabled
- **THEN** the default visible league leader category MUST remain visible and no core section MUST be hidden by a JavaScript-dependent mechanism

---

### Requirement: Print Stylesheet
The page MUST include a print stylesheet using `@media print`. Printed output SHALL resemble a newspaper supplement with appropriate typography, column layout, and removal of interactive controls.

#### Scenario: Print stylesheet present in rendered output
- **WHEN** an Edition JSON is rendered
- **THEN** the HTML output MUST contain a `@media print` CSS block or a linked stylesheet with `media="print"`

---

### Requirement: Visual Design Language
The visual design SHALL use: serif typography for headlines and body text, multi-column editorial layouts, thin and double horizontal rules for section separation, a restrained color palette, a newsprint-inspired background, compact tables, drop caps on lead story paragraphs, and small uppercase labels for section headings and metadata. The page SHALL NOT use: large rounded cards, app-style floating action controls, excessive gradients, horizontal carousels for core content, or heavy animation.

#### Scenario: Rendered page uses serif typography
- **WHEN** an Edition JSON is rendered
- **THEN** the CSS MUST declare a serif font family as the primary typeface for headline and body text elements

---

### Requirement: Responsive Layout
The page MUST be responsive across three breakpoints: desktop (multi-column layout), tablet (two-column layout), and mobile (single-column layout).

#### Scenario: Responsive layout breakpoints defined
- **WHEN** an Edition JSON is rendered
- **THEN** the CSS MUST include `@media` breakpoints that define multi-column, two-column, and single-column layouts

---

### Requirement: SEO Metadata
Each rendered page MUST include: a unique `<title>` tag, a `<meta name="description">` tag, a `<link rel="canonical">` tag, Open Graph metadata tags (`og:title`, `og:description`, `og:type`, `og:url`), and structured article metadata.

#### Scenario: SEO metadata present in rendered output
- **WHEN** an Edition JSON is rendered
- **THEN** the HTML `<head>` MUST contain all required SEO metadata elements with non-empty values

---

### Requirement: Edition ID Meta Tag
Each rendered edition MUST include a `<meta name="sportzballz-edition-id">` tag containing the edition's `id` value.

#### Scenario: Edition ID meta tag present
- **WHEN** an Edition JSON is rendered
- **THEN** the HTML output MUST contain `<meta name="sportzballz-edition-id" content="<edition-id>">` in the `<head>`

---

### Requirement: Deterministic HTML Output
HTML output MUST be deterministic for the same Edition JSON input. Rendering the same Edition JSON twice MUST produce identical HTML output, with no timestamps, random values, or non-deterministic ordering introduced by the renderer itself.

#### Scenario: Same Edition JSON produces identical HTML output
- **WHEN** the renderer processes the same Edition JSON document twice in succession
- **THEN** the two HTML outputs MUST be byte-for-byte identical

---

### Requirement: WCAG 2.2 AA Compliance
The rendered page MUST target WCAG 2.2 Level AA accessibility. This MUST include at minimum: a skip-to-content link, sufficient color contrast ratios, ARIA landmark roles on major sections, and keyboard navigability of interactive controls.

#### Scenario: Skip-to-content link present
- **WHEN** an Edition JSON is rendered
- **THEN** the HTML output MUST include a skip navigation link as the first focusable element on the page

---

### Requirement: HTML Output Size
HTML output MUST be under 500 KB where practical. If total page size exceeds 500 KB due to embedded data, the renderer MUST log a warning identifying the contributing sections.

#### Scenario: Standard edition renders under 500 KB
- **WHEN** a typical Edition JSON (full game day, all sections populated) is rendered
- **THEN** the resulting HTML file size MUST be under 500 KB

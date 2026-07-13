# Rendering

Template system, visual design, and asset reference for the SportzBallz Daily Sports Page.

---

## How the Jinja2 Template System Works

`HTMLRenderer` (`src/renderer/html_renderer.py`) loads templates using Jinja2's `FileSystemLoader` pointed at the `templates/` directory. Autoescaping is enabled for all `.html.j2` files to prevent XSS from any data that flows through from the API.

The renderer accepts a validated `Edition` object and a `RenderConfig` (output path, base URL, build timestamp). It calls `env.get_template("index.html.j2").render(edition=edition, config=render_config)` and writes the result to the staging directory.

```python
# src/renderer/html_renderer.py (simplified)
from jinja2 import Environment, FileSystemLoader, select_autoescape

env = Environment(
    loader=FileSystemLoader("templates"),
    autoescape=select_autoescape(["html.j2"]),
)
html = env.get_template("index.html.j2").render(edition=edition, config=config)
```

Output is deterministic: the same `Edition` object always produces byte-for-byte identical HTML.

---

## Template Directory Structure

```
templates/
├── index.html.j2               ← root layout; assembles all sections
└── sections/
    ├── header.html.j2          ← masthead, edition date/type, dateline
    ├── lead_story.html.j2      ← lead story with headline and body
    ├── secondary_stories.html.j2
    ├── scores.html.j2          ← game score grid
    ├── standings.html.j2       ← division tables + wild card
    ├── league_leaders.html.j2  ← stat leader tables (batting + pitching)
    ├── transactions.html.j2    ← transaction log
    ├── injuries.html.j2        ← injury report
    └── footer.html.j2          ← timestamps, data attribution, legal
```

`index.html.j2` uses Jinja2 `{% include %}` to pull in each section:

```jinja
{% include "sections/header.html.j2" %}
{% include "sections/lead_story.html.j2" %}
{% include "sections/scores.html.j2" %}
{# ... etc #}
```

---

## How to Modify a Section Template

1. Open the relevant file in `templates/sections/`.
2. Variables available in every section template:
   - `edition` — the full `Edition` object (see [edition-schema.md](edition-schema.md))
   - `config.base_url` — the public base URL
   - `config.build_timestamp` — ISO timestamp of this render
3. Edit the template. All HTML is autoescaped; use `{{ value | safe }}` only where you intentionally trust the content (story body is marked safe after validation).
4. Run a render to verify:
   ```bash
   daily-sports-page render --edition-json build/2026-07-13-0600/edition.json
   ```
5. Open the staged `index.html` in a browser to review.

---

## CSS Design Principles

The page targets a newspaper aesthetic:

- **Serif typography** — headlines in a classic serif (Georgia or similar); body text in a readable serif stack
- **Newsprint background** — off-white (`#f5f0e8`) background mimicking paper stock
- **Multi-column layout** — CSS `column-count` on body sections for a broadsheet feel; collapses to single column on narrow viewports
- **Subdued palette** — black text, dark red accents for section headers, no bright UI colors
- **Print-first sizing** — base font and spacing calibrated for letter-size print

---

## Static Assets

### CSS

**File:** `static/css/daily-sports-page.css`

All styles for the edition. Key sections within the file:

| Section                     | What it covers                   |
| --------------------------- | -------------------------------- |
| `:root` variables           | Typefaces, colors, column widths |
| `.masthead`                 | Nameplate, date, edition type    |
| `.story`                    | Lead and secondary story layout  |
| `.scores-grid`              | Score card grid                  |
| `.standings-table`          | Division standings tables        |
| `.leaders-table`            | Stat leader tables               |
| `.transactions-list`        | Transaction entries              |
| `.injury-list`              | Injury entries                   |
| `@media (max-width: 768px)` | Mobile single-column overrides   |
| `@media print`              | Print stylesheet (see below)     |

### JavaScript

**File:** `static/js/daily-sports-page.js`

Progressive enhancement only — the page is fully readable with JS disabled.

| Feature          | What it does                                                        |
| ---------------- | ------------------------------------------------------------------- |
| Tab switcher     | Toggles between AL/NL on standings and league leader sections       |
| Copy link        | "Copy link" button on each story copies the anchor URL to clipboard |
| Section collapse | Click section header to collapse/expand on mobile                   |
| Print            | `window.print()` call wired to the print button in the toolbar      |

---

## How to Change the Publication Name

The nameplate text is read from `config/settings.yaml`:

```yaml
publication:
  name: "SportzBallz Daily Sports Page"
  tagline: "All the scores that are fit to print"
  timezone: "America/New_York"
```

Change `name` and `tagline` there. The `header.html.j2` template reads these values from `config`, which is injected into the render context alongside `edition`.

---

## How to Add a New Section

Follow these steps to add a new section (e.g., a "Power Rankings" section):

1. **Add the section template**
   Create `templates/sections/power_rankings.html.j2`. Use `edition.powerRankings` as the data source.

2. **Add the section ID to the spec**
   Add `power_rankings` to the `sections` list in `config/settings.yaml` so the pipeline knows to populate it.

3. **Include it in `index.html.j2`**
   Add `{% include "sections/power_rankings.html.j2" %}` in the appropriate position.

4. **Add a Pydantic model if needed**
   If the section has new data structures, add a model in `src/models/`. Import and use it in `NormalizedData` and `Edition`.

5. **Populate the data in `EditorialEngine`**
   In `src/editorial/editorial_engine.py`, collect and assign the new data to `edition.powerRankings` during assembly.

6. **Add a normalizer method**
   In `src/normalizer/normalizer.py`, add a method to convert the raw API response for the new section.

7. **Render and review**
   Run a dry-run to verify the section appears correctly:
   ```bash
   daily-sports-page run --dry-run --date 2026-07-13
   ```

---

## Print Stylesheet

The `@media print` block in `static/css/daily-sports-page.css` targets letter-size output (8.5 × 11 in).

**Hidden when printing:**

- Navigation and tab switcher controls
- The copy-link and collapse buttons
- Footer links and legal boilerplate
- The print toolbar itself

**Print-specific overrides:**

- Background color set to white; newsprint tint removed
- All columns print on a white background with black text
- Page breaks avoided within individual stories (`page-break-inside: avoid`)
- Font sizes adjusted slightly for print density

To preview the print layout in Chrome: open the edition in a browser, open DevTools, toggle the print media emulator under the Rendering panel.

## ADDED Requirements

### Requirement: Division and Wild-Card Standings Calculation
The statistical processor MUST calculate standings for all six MLB divisions (AL East, AL Central, AL West, NL East, NL Central, NL West) and both wild-card pools (AL wild card, NL wild card).

#### Scenario: Standings calculated for all six divisions
- **WHEN** the statistical processor runs
- **THEN** standings rows MUST be produced for all six divisions, each containing all teams in that division

#### Scenario: Wild-card standings calculated for both leagues
- **WHEN** the statistical processor runs
- **THEN** wild-card pool standings MUST be produced for both the AL and NL, including `wcGb` values for all rows

---

### Requirement: Standings Row Fields
Standings MUST include for each team: `wins`, `losses`, `pct` (win percentage to three decimal places), `gb` (games behind division leader, or `"-"` for leader), `wcGb` (games behind wild-card cutline where applicable), `last10` (record over last 10 games in `"W-L"` format), `streak` (current winning or losing streak, e.g., `"W3"`), `homeRecord`, `awayRecord`, and `runDifferential` (signed integer).

#### Scenario: Division leader GB is dash
- **WHEN** standings are calculated for a division
- **THEN** the team with the best record MUST have `gb` set to `"-"`

#### Scenario: Run differential is a signed integer
- **WHEN** standings rows are generated
- **THEN** `runDifferential` MUST be a signed integer (positive for runs scored lead, negative for deficit)

---

### Requirement: League Leaders by Category
The statistical processor MUST rank players for each required batting and pitching category. Required batting categories MUST include at minimum: batting average (AVG), on-base percentage (OBP), slugging percentage (SLG), on-base plus slugging (OPS), home runs (HR), runs batted in (RBI), runs scored (R), stolen bases (SB), hits (H), doubles (2B), triples (3B), walks (BB), strikeouts (SO). Required pitching categories MUST include at minimum: earned run average (ERA), wins (W), strikeouts (SO), WHIP, innings pitched (IP), saves (SV), holds (HLD), quality starts (QS), complete games (CG), shutouts (SHO), batting average against (BAA), home runs allowed (HRA), walks issued (BB), strikeouts per nine innings (K/9), walk-plus-hit per inning pitched (WHIP).

#### Scenario: Top-10 batting average leaders generated
- **WHEN** the statistical processor calculates league leaders for batting average
- **THEN** the output MUST contain up to 10 entries ranked by AVG, including only qualified batters

#### Scenario: All required batting and pitching categories are present
- **WHEN** the statistical processor generates league leaders
- **THEN** leader lists MUST be present for all 13 required batting categories and all 15 required pitching categories

---

### Requirement: League Leader Top 10
League leader lists MUST show the top 10 qualified players per category. If fewer than 10 players qualify, the list MUST include all qualifying players.

#### Scenario: Leader list contains at most 10 entries
- **WHEN** a league leader category is generated
- **THEN** the list MUST contain no more than 10 entries

#### Scenario: Fewer than 10 qualifiers produces shorter list
- **WHEN** fewer than 10 players meet the qualification threshold for a category
- **THEN** the list MUST contain exactly the number of qualifying players without padding

---

### Requirement: Player Qualification
Player qualification for batting leaders MUST be determined using the standard MLB threshold of plate appearances per team game played. Player qualification for pitching leaders MUST be determined using innings pitched per team game played. Unqualified players MUST have `isQualified` set to `false` and MUST NOT appear in the default top-10 qualified list.

#### Scenario: Qualification filtering removes ineligible batters
- **WHEN** league leaders are calculated for a batting category
- **THEN** players below the PA-per-team-game threshold MUST be excluded from the qualified top-10 list

#### Scenario: Unqualified pitcher flagged correctly
- **WHEN** a pitcher appears in leader data but does not meet the IP-per-team-game threshold
- **THEN** `isQualified` MUST be `false` on their entry

---

### Requirement: Derived Game Metrics
The statistical processor MUST calculate the following derived metrics for each completed game: largest deficit overcome (comeback run differential), margin of victory, extra-inning flag (boolean), walk-off flag (boolean), and no-hitter status (enum: `none`, `no_hitter_in_progress`, `no_hitter_complete`, `perfect_game_in_progress`, `perfect_game_complete`).

#### Scenario: Walk-off game detection
- **WHEN** the home team scores the winning run in the bottom of the final inning
- **THEN** the game record MUST have `walkOff` set to `true`

#### Scenario: Extra-inning game detection
- **WHEN** a game ends after more than 9 innings
- **THEN** the game record MUST have `extraInnings` set to `true`

#### Scenario: Comeback detection
- **WHEN** the winning team trailed by the largest deficit overcome during the game
- **THEN** `largestDeficitOvercome` MUST record the maximum run deficit the winning team faced at any point

---

### Requirement: Notable Performance Detection
The statistical processor MUST identify and flag notable performances including: no-hitter or perfect-game attempts in progress or completed, record-setting individual or team performances, and milestone approaches (e.g., approaching 500 career home runs, approaching 3,000 hits).

#### Scenario: No-hitter in progress detected
- **WHEN** a pitcher has retired all batters faced through six or more innings with no hits allowed
- **THEN** `noHitterStatus` MUST be set to `no_hitter_in_progress`

#### Scenario: Completed no-hitter flagged
- **WHEN** a game ends with no hits allowed by the pitching team
- **THEN** `noHitterStatus` MUST be set to `no_hitter_complete`

---

### Requirement: Editorial Ranking Signals
The statistical processor MUST generate editorial ranking signals as structured data to serve as inputs to the lead-story scoring model. Signals MUST include numeric scores or boolean flags for: game leverage (based on standings implications), comeback size, walk-off status, extra-inning status, no-hitter status, notable individual performance flag, and rivalry flag.

#### Scenario: Editorial signals generated for each completed game
- **WHEN** statistical processing completes for a set of games
- **THEN** each completed game MUST have an associated editorial signal object containing all required signal fields

---

### Requirement: Statistical Processor Does Not Generate HTML or Make HTTP Requests
The statistical processor MUST NOT produce HTML output. The statistical processor MUST NOT make HTTP requests. All input data MUST come from the normalized internal models produced by the normalization stage.

#### Scenario: Statistical processor runs without network access
- **WHEN** the statistical processor executes in an environment with no network access
- **THEN** it MUST complete without error using only its normalized model inputs

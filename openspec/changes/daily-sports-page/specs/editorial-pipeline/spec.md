## ADDED Requirements

### Requirement: Lead Story Selection via Weighted Scoring Model
The editorial engine MUST select the lead story using a configurable weighted scoring model applied to all candidate stories. The highest-scoring candidate MUST be selected unless a manual override is active.

#### Scenario: Lead story selected by highest score
- **WHEN** the editorial engine evaluates candidates and no manual override is set
- **THEN** the candidate with the highest weighted score MUST be selected as the lead story

---

### Requirement: Lead Story Scoring Factors
The lead-story scoring model MUST consider the following factors, each with a configurable weight: playoff importance, historic significance, game leverage (standings implications), market and national relevance, individual performance, comeback size, walk-off status, extra-inning status, rivalry significance, no-hitter status, record or milestone proximity, trade significance, and injury significance.

#### Scenario: No-hitter completion elevates score
- **WHEN** a completed no-hitter is present in the game data
- **THEN** the no-hitter game MUST receive a non-zero boost from the `noHitter` scoring factor, increasing its total weighted score

#### Scenario: Walk-off game scoring factor applied
- **WHEN** a game is flagged as a walk-off
- **THEN** the `walkOff` scoring factor weight MUST be applied to that game's score

---

### Requirement: Configurable Scoring Weights
All scoring weights for the lead-story model MUST be defined in `config/editorial.yaml`. Weights MUST NOT be hardcoded in application source code. Changes to weights MUST take effect on the next generation run without code changes.

#### Scenario: Scoring weights loaded from config file
- **WHEN** the editorial engine initializes
- **THEN** it MUST load all scoring weights from `config/editorial.yaml` and MUST NOT use any hardcoded weight values

---

### Requirement: Manual Editorial Overrides
The editorial engine MUST support manual overrides via configuration. Supported overrides MUST include: `lead_story_game_id` (force a specific game as the lead), `featured_player_ids` (ensure specific players appear in secondary stories), and `suppress_story_ids` (exclude specific games or stories from all editorial output).

#### Scenario: Manual lead story override respected
- **WHEN** `lead_story_game_id` is set in the override configuration
- **THEN** the editorial engine MUST select that game as the lead story regardless of scoring model output

#### Scenario: Suppressed story excluded from all output
- **WHEN** a game ID appears in `suppress_story_ids`
- **THEN** that game MUST NOT appear as a lead story, secondary story, or game recap entry

---

### Requirement: Secondary Story Selection
The editorial engine MUST select between 3 and 6 secondary stories from remaining candidates after lead story selection. Secondary stories MUST NOT duplicate the lead story. Featured player stories MUST be included if `featured_player_ids` overrides are set and qualifying content exists.

#### Scenario: Secondary story count within bounds
- **WHEN** the editorial engine selects secondary stories
- **THEN** the count MUST be at least 3 and at most 6

#### Scenario: Featured player appears in secondary stories
- **WHEN** `featured_player_ids` contains a player ID and content referencing that player is available
- **THEN** at least one secondary story referencing that player MUST be included

---

### Requirement: AI Generation Prompt Content
AI generation prompts MUST include all of the following: relevant structured game data, player statistics, standings context, known injuries, transaction data, required article format specification, maximum article length, and an explicit prohibition on claims not supported by the provided data.

#### Scenario: AI prompt includes structured game data and prohibition clause
- **WHEN** the editorial engine constructs an AI generation prompt
- **THEN** the prompt MUST include structured game data for the story subject and an explicit instruction prohibiting unsupported claims

---

### Requirement: AI Output Format
AI output MUST use a structured JSON format with the following fields: `headline` (string), `deck` (string), `paragraphs` (array of strings), and `factsUsed` (array of source fact references corresponding to data points cited in the text).

#### Scenario: AI generation returns required JSON structure
- **WHEN** the AI provider returns a successful response
- **THEN** the response MUST be parseable as JSON containing `headline`, `deck`, `paragraphs`, and `factsUsed`

---

### Requirement: Source Fact Attachment
The editorial engine MUST attach the `factsUsed` array from AI output to the generated story object, linking each story to the specific data points it references.

#### Scenario: Generated story has source facts attached
- **WHEN** the editorial engine processes AI output
- **THEN** the resulting story object MUST include a `sourceDataReferences` field populated from `factsUsed`

---

### Requirement: Prohibited AI Fabrications
The editorial engine MUST NOT permit AI-generated content to contain: invented quotes, unverified injury information, unverified transactions, betting lines, attendance figures not in source data, weather information not in source data, statistics not present in source data, standings implications not derivable from source data, or record or milestone claims not present in source data.

#### Scenario: AI fabrication detected and rejected
- **WHEN** AI output contains a statistic or claim not traceable to the provided source data
- **THEN** the content validator MUST reject the story and the editorial engine MUST fall back to the deterministic template for that story slot

---

### Requirement: Deterministic Fallback Templates
The editorial engine MUST use deterministic fallback templates to generate story content when the AI provider is unavailable or returns invalid output. Fallback templates MUST produce grammatically complete stories using only verified source data.

#### Scenario: AI provider failure triggers fallback template
- **WHEN** the AI provider returns an error or times out
- **THEN** the editorial engine MUST generate the story using the deterministic fallback template and MUST NOT block publication

#### Scenario: Fallback does not block scores and standings
- **WHEN** the AI provider is unavailable and fallback templates are used
- **THEN** scores, standings, schedule data, league leaders, transactions, and injuries MUST still be published

---

### Requirement: Editorial Neutrality
The front page MUST NOT be tailored primarily to any single team. The scoring model and story selection MUST produce editorially balanced output across the league.

#### Scenario: No single team dominates all story slots
- **WHEN** the editorial engine selects the lead story and all secondary stories
- **THEN** no single team MUST appear as the primary subject of more than half of all editorial story slots in a single edition

---

### Requirement: Game Recap Ordering and Labels
Game recaps MUST be ordered by editorial significance rather than start time alone. Each game recap MUST include applicable special labels from the following set: `walk-off`, `extra-inning`, `comeback`, `upset`, `best-pitching`, `highest-scoring`, `most-important-standings-result`.

#### Scenario: Game recaps ordered by editorial significance
- **WHEN** game recaps are assembled for the edition
- **THEN** recaps MUST be ordered by the editorial scoring model output, not solely by scheduled start time

#### Scenario: Walk-off label applied to qualifying game
- **WHEN** a game is flagged as a walk-off in the derived metrics
- **THEN** its recap MUST include the `walk-off` label

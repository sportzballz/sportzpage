# Game Recap Generation Prompt

Write a short game recap for the SportzBallz Daily Sports Page.

## Requirements

- Headline: "[Winner] [Score], [Loser] [Score]" format or creative variant.
- Deck: one sentence summary.
- Body: 1-3 paragraphs.
- Reference only facts in the provided game data.
- Do NOT invent quotes, statistics, or play-by-play not in the data.
- Style: traditional newspaper sports prose.

## Output Format (JSON)

```json
{
  "headline": "string",
  "deck": "string",
  "paragraphs": ["paragraph1", "..."],
  "factsUsed": ["fact_id"]
}
```

## Game Data

{{ game | tojson(indent=2) }}

# League Roundup Generation Prompt

Write a brief "Around the League" item for the SportzBallz Daily Sports Page.

## Item Type

{{ item_type }}

## Requirements

- 2-4 sentences of newspaper prose.
- Factual — every claim must reference provided data.
- Do NOT invent statistics, standings implications, or transactions.

## Output Format (JSON)

```json
{
  "headline": "string",
  "deck": "string",
  "paragraphs": ["string"],
  "factsUsed": ["fact_id"]
}
```

## Data

{{ data | tojson(indent=2) }}

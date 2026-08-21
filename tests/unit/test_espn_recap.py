import json

import pytest

from src.editorial.espn_recap import ESPNLeadStoryService


def test_parses_structured_espn_recap_page() -> None:
    payload = {
        "page": {
            "content": {
                "fullGmStry": {
                    "hdln": "Braves win 2-0",
                    "bdy": "<p>Grant Holmes carried a no-hitter into the seventh.</p>",
                }
            }
        }
    }
    html = f"<script>window['__espnfitt__']={json.dumps(payload)};</script>"

    story = ESPNLeadStoryService.parse_page(html)

    assert story is not None
    assert story["hdln"] == "Braves win 2-0"


def test_parses_model_json_code_fence() -> None:
    text = '```json\n{"headline":"A","deck":"B","paragraphs":["1","2","3"]}\n```'

    story = ESPNLeadStoryService._parse_model_json(text)

    assert story["paragraphs"] == ["1", "2", "3"]


def test_grounding_rejects_unsupported_number() -> None:
    with pytest.raises(ValueError, match="unsupported numbers"):
        ESPNLeadStoryService._validate_grounding("He retired 24 hitters.", "He retired 18.")


def test_grounding_rejects_invented_division_rivalry() -> None:
    with pytest.raises(ValueError, match="division rivals"):
        ESPNLeadStoryService._validate_grounding(
            "The division rivals met Thursday.",
            "The matchup was between division leaders.",
        )


def test_extracts_text_from_openai_response() -> None:
    result = {
        "output": [
            {
                "type": "message",
                "content": [
                    {
                        "type": "output_text",
                        "text": '{"headline":"A","deck":"B","paragraphs":["1","2","3"]}',
                    }
                ],
            }
        ]
    }

    text = ESPNLeadStoryService._extract_output_text(result)

    assert json.loads(text)["headline"] == "A"


def test_missing_openai_key_falls_back_without_calling_api() -> None:
    service = ESPNLeadStoryService(provider="openai", api_key="")

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        import asyncio

        asyncio.run(service._rewrite_with_openai("prompt"))

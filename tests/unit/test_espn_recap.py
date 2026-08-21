import json
from pathlib import Path

import pytest

from src.editorial.espn_recap import ESPNLeadStoryService, ESPNRecap
from src.models.game import Game, GameStatus, TeamGameLine
from src.models.story import GameRecap, StoryType


def _game() -> Game:
    return Game(
        game_id=123,
        espn_game_id="401877087",
        game_date="2026-08-20",
        status=GameStatus.final,
        away=TeamGameLine(team_id=1, team_abbr="ATL", team_name="Braves", runs=2),
        home=TeamGameLine(team_id=2, team_abbr="CWS", team_name="White Sox", runs=0),
    )


def _recap() -> GameRecap:
    return GameRecap(
        headline="Cached lead",
        deck="Cached deck",
        byline="SportzBallz Staff",
        paragraphs=["One.", "Two.", "Three."],
        source_data_references=["game:123", "espn:401877087"],
        story_type=StoryType.game_recap,
        teams=["ATL", "CWS"],
        facts_used=["espn_game_id:401877087"],
        ai_generated=True,
        source_name="ESPN recap",
        source_url="https://www.espn.com/mlb/recap/_/gameId/401877087",
        game_id=123,
        final_score="ATL 2, CWS 0",
    )


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


def test_parses_espn_summary_article() -> None:
    payload = {
        "article": {
            "headline": "Braves win 2-0",
            "story": "<p>Grant Holmes carried a no-hitter into the seventh.</p>",
        }
    }

    story = ESPNLeadStoryService.parse_summary(payload)

    assert story == {
        "hdln": "Braves win 2-0",
        "bdy": "<p>Grant Holmes carried a no-hitter into the seventh.</p>",
    }


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


@pytest.mark.asyncio
async def test_reuses_daily_cached_recap_without_fetch_or_llm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ESPNLeadStoryService(provider="openai", api_key="unused", cache_dir=tmp_path)
    game = _game()
    service._save_cached(game, _recap())

    async def should_not_fetch(_game_id: str) -> ESPNRecap | None:
        raise AssertionError("ESPN and OpenAI must not be called when today's recap is cached")

    monkeypatch.setattr(service, "fetch", should_not_fetch)

    result = await service.generate(game)

    assert result is not None
    assert result.headline == "Cached lead"


@pytest.mark.asyncio
async def test_reuses_daily_cached_short_recap_without_fetch_or_llm(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = ESPNLeadStoryService(provider="openai", api_key="unused", cache_dir=tmp_path)
    game = _game()
    short = _recap().model_copy(update={"paragraphs": ["Two lively sentences. Still brief."]})
    service._save_cached(game, short, short=True)

    async def should_not_fetch(_game_id: str) -> ESPNRecap | None:
        raise AssertionError("ESPN and OpenAI must not be called when today's recap is cached")

    monkeypatch.setattr(service, "fetch", should_not_fetch)

    result = await service.generate(game, short=True)

    assert result is not None
    assert result.paragraphs == ["Two lively sentences. Still brief."]
    assert service._cache_path(game, short=True).name.endswith("-short.json")


def test_short_recap_prompt_and_output_are_concise() -> None:
    service = ESPNLeadStoryService()
    source = ESPNRecap(
        game_id="401877087",
        headline="Braves win",
        body="The Braves won 2-0 behind Grant Holmes.",
        source_url="https://www.espn.com/mlb/recap/_/gameId/401877087",
    )
    text = json.dumps(
        {
            "headline": "Holmes Sets the Tone",
            "deck": "Atlanta rode its starter to a crisp victory.",
            "paragraphs": [
                "Grant Holmes carried Atlanta through the afternoon. "
                "The Braves turned his work into a 2-0 win."
            ],
        }
    )

    result = service._build_game_recap(text, source, _game(), short=True)

    assert len(result.paragraphs) == 1
    assert "2 to 3 concise sentences" in service._prompt(source, _game(), short=True)

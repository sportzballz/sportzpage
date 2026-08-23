from datetime import date
from pathlib import Path

import httpx
import pytest

from src.football.ai_recap import FootballLeadStoryService
from src.football.generator import FootballEditionGenerator


def _event(event_id: str, away: str, home: str, completed: bool = True) -> dict:
    return {
        "id": event_id,
        "name": f"{away} at {home}",
        "date": "2026-08-20T23:00Z",
        "competitions": [{
            "venue": {"fullName": "The Linc"},
            "competitors": [
                {"homeAway": "away", "score": "17", "winner": False, "team": {"abbreviation": away, "displayName": away}},
                {"homeAway": "home", "score": "24", "winner": True, "team": {"abbreviation": home, "displayName": home}},
            ],
            "status": {"type": {"description": "Final", "completed": completed}},
        }],
    }


def test_parses_espn_nfl_scoreboard_event() -> None:
    games = FootballEditionGenerator._games({"events": [_event("401", "NYG", "PHI")]})

    assert games[0]["home"]["abbr"] == "PHI"
    assert games[0]["home"]["score"] == "24"
    assert games[0]["venue"] == "The Linc"
    assert games[0]["recap_url"].endswith("/401")


def test_lead_prioritizes_eagles_then_nfc_east() -> None:
    games = FootballEditionGenerator._games({"events": [
        _event("1", "GB", "CHI"),
        _event("2", "DAL", "LV"),
        _event("3", "NYG", "PHI"),
    ]})

    lead = FootballEditionGenerator._select_lead(games)

    assert lead is not None
    assert "PHI" in lead["deck"]


def test_generator_accepts_explicit_edition_date() -> None:
    generator = FootballEditionGenerator(date(2026, 8, 20))

    assert generator.edition_date.isoformat() == "2026-08-20"


def test_parses_nfl_league_leaders_in_display_order() -> None:
    def category(name: str, label: str, player: str, team: str, value: str) -> dict:
        return {
            "name": name,
            "displayName": label,
            "abbreviation": "YDS",
            "leaders": [
                {
                    "displayValue": value,
                    "athlete": {
                        "displayName": player,
                        "position": {"abbreviation": "QB"},
                        "links": [
                            {
                                "rel": ["playercard", "desktop"],
                                "href": "https://www.espn.com/nfl/player/example",
                            }
                        ],
                    },
                    "team": {"abbreviation": team},
                }
            ],
        }

    payload = {
        "leaders": {
            "categories": [
                category("sacks", "Sacks", "Defender", "PHI", "18"),
                category("passingYards", "Passing Yards", "Quarterback", "BUF", "4,500"),
                category("rushingYards", "Rushing Yards", "Runner", "BAL", "1,500"),
            ]
        }
    }

    leaders = FootballEditionGenerator._league_leaders(payload)

    assert [item["name"] for item in leaders] == ["passingYards", "rushingYards", "sacks"]
    assert leaders[0]["rows"][0] == {
        "rank": 1,
        "name": "Quarterback",
        "position": "QB",
        "team": "BUF",
        "value": "4,500",
        "url": "https://www.espn.com/nfl/player/example",
    }


def test_nfl_league_leaders_limit_each_category_to_five() -> None:
    payload = {
        "leaders": {
            "categories": [
                {
                    "name": "passingYards",
                    "displayName": "Passing Yards",
                    "abbreviation": "YDS",
                    "leaders": [
                        {
                            "displayValue": str(5000 - rank),
                            "athlete": {"displayName": f"Player {rank}"},
                            "team": {"abbreviation": "PHI"},
                        }
                        for rank in range(1, 8)
                    ],
                }
            ]
        }
    }

    leaders = FootballEditionGenerator._league_leaders(payload)

    assert len(leaders[0]["rows"]) == 5
    assert [row["rank"] for row in leaders[0]["rows"]] == [1, 2, 3, 4, 5]


def test_nfl_leaders_season_label() -> None:
    payload = {"requestedSeason": {"year": 2026, "type": {"name": "Preseason"}}}

    assert FootballEditionGenerator._leaders_season_label(payload) == "2026 Preseason"


@pytest.mark.asyncio
async def test_football_lead_reuses_daily_cache_without_api_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = FootballEditionGenerator._games({"events": [_event("401", "NYG", "PHI")]})[0]
    service = FootballLeadStoryService(api_key="unused", cache_dir=tmp_path)
    cached = {
        "headline": "Cached Eagles Lead",
        "deck": "The published copy stays put.",
        "paragraphs": ["One.", "Two.", "Three."],
        "url": game["recap_url"],
        "ai_generated": True,
        "espn_game_id": "401",
        "edition_date": "2026-08-20",
    }
    service._save_cached(game, "2026-08-20", cached)

    async def should_not_fetch(_game_id: str) -> str | None:
        raise AssertionError("ESPN and OpenAI must not be called for a cached NFL lead")

    monkeypatch.setattr(service, "_fetch_recap", should_not_fetch)
    result = await service.generate(game, "2026-08-20")

    assert result == cached
    assert service.cache_path(game, "2026-08-20").name == "nfl-2026-08-20-401.json"


@pytest.mark.asyncio
async def test_optional_nfl_data_failure_degrades_to_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = FootballEditionGenerator(date(2026, 8, 20))

    async def fail(*_args: object, **_kwargs: object) -> dict:
        raise httpx.ConnectError("ESPN unavailable")

    monkeypatch.setattr(generator, "_get", fail)

    async with httpx.AsyncClient() as client:
        assert await generator._get_optional(client, "https://example.com", {}) == {}

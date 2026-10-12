from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.nba.ai_recap import NBALeadStoryService
from src.nba.generator import BASKETBALL_TEAMS, _games, _news_candidates, _standings, generate


def test_nba_game_and_conference_parsing() -> None:
    games = _games(
        {
            "events": [
                {
                    "id": "401",
                    "date": "2026-10-11T23:30Z",
                    "status": {"type": {"completed": True, "shortDetail": "Final"}},
                    "competitions": [
                        {
                            "competitors": [
                                {
                                    "homeAway": "away",
                                    "score": "112",
                                    "team": {
                                        "displayName": "Philadelphia 76ers",
                                        "abbreviation": "PHI",
                                    },
                                },
                                {
                                    "homeAway": "home",
                                    "score": "108",
                                    "team": {
                                        "displayName": "Boston Celtics",
                                        "abbreviation": "BOS",
                                    },
                                },
                            ]
                        }
                    ],
                }
            ]
        }
    )
    assert games[0]["completed"] is True
    assert games[0]["away"]["abbreviation"] == "PHI"
    assert games[0]["date"] == "2026-10-11"
    assert BASKETBALL_TEAMS["new-york"] == ("NY", "BKN")

    conferences = _standings(
        {
            "children": [
                {
                    "name": "Eastern Conference",
                    "standings": {
                        "entries": [
                            {
                                "team": {"displayName": "Boston Celtics"},
                                "stats": [
                                    {"name": "wins", "displayValue": "8"},
                                    {"name": "losses", "displayValue": "2"},
                                    {"name": "winPercent", "displayValue": ".800"},
                                    {"name": "gamesBehind", "displayValue": "-"},
                                    {"name": "streak", "displayValue": "W3"},
                                    {"name": "playoffSeed", "displayValue": "1"},
                                ],
                            }
                        ]
                    },
                }
            ]
        }
    )
    assert conferences[0]["name"] == "Eastern Conference"
    assert conferences[0]["rows"][0]["pct"] == ".800"


def test_nba_news_candidates_prioritize_local_and_do_not_expose_links() -> None:
    payload = {
        "articles": [
            {
                "id": 1,
                "headline": "Around the NBA",
                "links": {
                    "api": {"self": {"href": "https://content.core.api.espn.com/v1/news/1"}}
                },
            },
            {
                "id": 2,
                "headline": "Sixers make a move",
                "categories": [{"type": "team", "abbreviation": "PHI"}],
                "links": {
                    "api": {"self": {"href": "https://content.core.api.espn.com/v1/news/2"}}
                },
            },
        ]
    }
    candidates = _news_candidates(payload, ("PHI",))
    assert [item["id"] for item in candidates] == ["2", "1"]
    assert "url" not in candidates[0]


@pytest.mark.asyncio
async def test_nba_rejects_non_ap_news_and_does_not_cache_it(
    tmp_path: Path, monkeypatch
) -> None:
    service = NBALeadStoryService(api_key="test", cache_dir=tmp_path)
    article = {
        "id": "9",
        "headline": "Example",
        "api_url": "https://content.core.api.espn.com/v1/sports/news/9",
    }

    async def non_ap(_url: str) -> None:
        return None

    monkeypatch.setattr(service, "_fetch_news_article", non_ap)
    assert await service.generate_from_news(article, "2026-10-11") is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_nba_generates_all_market_pages_without_ai(
    tmp_path: Path, monkeypatch
) -> None:
    async def empty(_client, _url, _params):
        return {}

    monkeypatch.setattr("src.nba.generator._get", empty)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    await generate(date(2026, 10, 11), tmp_path)
    for market in BASKETBALL_TEAMS:
        page = json.loads((tmp_path / market / "edition.json").read_text())
        html = (tmp_path / market / "index.html").read_text()
        assert page["lead"] is None
        assert "NBA Standings" in html
        assert "No AP-sourced lead story is available" in html
        assert 'href="https://www.espn.com' not in html
    assert "NBA" in (tmp_path / "philadelphia" / "index.html").read_text()

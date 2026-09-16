from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.nhl.ai_recap import NHLLeadStoryService
from src.nhl.generator import HOCKEY_TEAMS, _games, _news_candidates, _standings, generate


def test_nhl_game_and_division_parsing() -> None:
    games = _games(
        {
            "events": [
                {
                    "id": "401",
                    "date": "2026-10-10T23:00Z",
                    "status": {"type": {"completed": True, "shortDetail": "Final"}},
                    "competitions": [
                        {
                            "competitors": [
                                {
                                    "homeAway": "away",
                                    "score": "3",
                                    "team": {"displayName": "Flyers", "abbreviation": "PHI"},
                                },
                                {
                                    "homeAway": "home",
                                    "score": "2",
                                    "team": {"displayName": "Bruins", "abbreviation": "BOS"},
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
    assert games[0]["date"] == "2026-10-10"
    assert HOCKEY_TEAMS["philadelphia"] == ("PHI",)
    divisions = _standings(
        {
            "children": [
                {
                    "children": [
                        {
                            "name": "Atlantic Division",
                            "standings": {
                                "entries": [
                                    {
                                        "team": {"displayName": "Bruins"},
                                        "stats": [
                                            {"name": "wins", "displayValue": "8"},
                                            {"name": "points", "displayValue": "17"},
                                        ],
                                    }
                                ]
                            },
                        }
                    ]
                }
            ]
        }
    )
    assert divisions[0]["name"] == "Atlantic Division"
    assert divisions[0]["rows"][0]["pts"] == "17"


def test_nhl_news_candidates_prioritize_local_and_do_not_expose_links() -> None:
    payload = {
        "articles": [
            {
                "id": 1,
                "headline": "Around the NHL",
                "links": {
                    "api": {"self": {"href": "https://content.core.api.espn.com/v1/sports/news/1"}}
                },
            },
            {
                "id": 2,
                "headline": "Flyers make a move",
                "categories": [{"type": "team", "abbreviation": "PHI"}],
                "links": {
                    "api": {"self": {"href": "https://content.core.api.espn.com/v1/sports/news/2"}}
                },
            },
        ]
    }
    candidates = _news_candidates(payload, ("PHI",))
    assert [item["id"] for item in candidates] == ["2", "1"]
    assert "url" not in candidates[0]


@pytest.mark.asyncio
async def test_nhl_rejects_non_ap_news_and_does_not_cache_it(tmp_path: Path, monkeypatch) -> None:
    service = NHLLeadStoryService(api_key="test", cache_dir=tmp_path)
    article = {
        "id": "9",
        "headline": "Example",
        "api_url": "https://content.core.api.espn.com/v1/sports/news/9",
    }

    async def non_ap(_url: str) -> None:
        return None

    monkeypatch.setattr(service, "_fetch_news_article", non_ap)
    assert await service.generate_from_news(article, "2026-09-15") is None
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_nhl_generates_all_market_pages_without_ai(tmp_path: Path, monkeypatch) -> None:
    async def empty(_client, _url, _params):
        return {}

    monkeypatch.setattr("src.nhl.generator._get", empty)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    await generate(date(2026, 9, 15), tmp_path)
    for market in HOCKEY_TEAMS:
        page = json.loads((tmp_path / market / "edition.json").read_text())
        html = (tmp_path / market / "index.html").read_text()
        assert page["lead"] is None
        assert "NHL Standings" in html
        assert "No AP-sourced lead story is available" in html
        assert 'href="https://www.espn.com' not in html
    assert "NHL" in (tmp_path / "philadelphia" / "index.html").read_text()

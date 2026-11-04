from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.mens_hoops.generator import COLLEGE_TEAMS, _games, _standings, generate


def test_mens_hoops_parses_games_and_limits_standings_to_major_conferences() -> None:
    games = _games(
        {
            "events": [
                {
                    "id": "401",
                    "date": "2026-11-02T00:00Z",
                    "status": {"type": {"completed": True, "shortDetail": "Final"}},
                    "competitions": [
                        {
                            "competitors": [
                                {"homeAway": "away", "score": "72", "team": {"displayName": "Notre Dame", "abbreviation": "ND"}},
                                {"homeAway": "home", "score": "74", "team": {"displayName": "Villanova", "abbreviation": "VILL"}},
                            ]
                        }
                    ],
                }
            ]
        }
    )
    assert games[0]["away"]["abbreviation"] == "ND"
    assert games[0]["home"]["score"] == "74"
    assert "VILL" in COLLEGE_TEAMS["philadelphia"]

    entry = {
        "team": {"displayName": "Example University"},
        "stats": [
            {"name": "wins", "displayValue": "8"},
            {"name": "losses", "displayValue": "2"},
            {"name": "winPercent", "displayValue": ".800"},
        ],
    }
    conferences = _standings(
        {
            "children": [
                {"name": "Big Ten Conference", "abbreviation": "big10", "standings": {"entries": [entry]}},
                {"name": "Mid-American Conference", "abbreviation": "midam", "standings": {"entries": [entry]}},
            ]
        }
    )
    assert [conference["name"] for conference in conferences] == ["Big Ten Conference"]


@pytest.mark.asyncio
async def test_mens_hoops_generates_every_market_without_ai(tmp_path: Path, monkeypatch) -> None:
    async def empty(_client, _url, _params):
        return {}

    monkeypatch.setattr("src.mens_hoops.generator._get", empty)
    monkeypatch.delenv("AI_PROVIDER", raising=False)
    await generate(date(2026, 11, 2), tmp_path)

    for market in COLLEGE_TEAMS:
        page = json.loads((tmp_path / market / "edition.json").read_text())
        html = (tmp_path / market / "index.html").read_text()
        assert page["lead"] is None
        assert "Major Conference Standings" in html
        assert ">Hoops</a>" in html
        assert 'href="https://www.espn.com' not in html

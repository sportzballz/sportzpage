from __future__ import annotations

import json
from datetime import date, datetime, timezone
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
    assert [conference["id"] for conference in conferences] == ["big10"]


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
        assert 'data-tablist-id="mens-hoops-conferences"' not in html
        assert ">Hoops</a>" in html
        assert f'href="/editions/{market}/mens-hoops/"' in html
        assert 'href="/static/css/daily-sports-page.css' in html
        assert 'href="https://www.espn.com' not in html


def test_mens_hoops_standings_render_one_tab_per_conference() -> None:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
    from src.rendering.edition_meta import daypart_edition, format_eastern_time, volume_number

    environment = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(["html", "xml"]),
    )
    environment.globals.update(
        daypart_edition=daypart_edition,
        format_eastern_time=format_eastern_time,
        volume_number=volume_number,
    )
    page = {
        "canonical_path": "/editions/philadelphia/mens-hoops/",
        "market_slug": "philadelphia",
        "market_label": "Philadelphia",
        "edition_date": date(2026, 11, 8),
        "generated_at": datetime(2026, 11, 8, 14, tzinfo=timezone.utc),
        "lead": None,
        "recent_games": [],
        "games": [],
        "upcoming_games": [],
        "conferences": [
            {"id": "acc", "name": "Atlantic Coast Conference", "rows": []},
            {"id": "sec", "name": "Southeastern Conference", "rows": []},
        ],
    }

    html = environment.get_template("mens_hoops.html.j2").render(page=page)

    assert 'data-tablist-id="mens-hoops-conferences"' in html
    assert 'id="mens-hoops-conference-tab-acc"' in html
    assert 'aria-controls="mens-hoops-conference-panel-sec"' in html
    assert html.count('role="tab"') == 2
    assert html.count('role="tabpanel"') == 2

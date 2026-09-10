from __future__ import annotations

from datetime import date
from pathlib import Path

from src.ncaaf.generator import NCAAFEditionGenerator


def _event(
    event_id: str,
    away: tuple[str, str, str, int],
    home: tuple[str, str, str, int],
    *,
    completed: bool = False,
) -> dict:
    def competitor(side: str, values: tuple[str, str, str, int], winner: bool) -> dict:
        team_id, name, conference_id, rank = values
        return {
            "homeAway": side,
            "winner": winner,
            "score": "24" if winner else "17",
            "team": {
                "id": team_id,
                "location": name,
                "abbreviation": name[:3].upper(),
                "conferenceId": conference_id,
            },
            "curatedRank": {"current": rank},
            "records": [{"summary": "1-0"}],
        }

    return {
        "id": event_id,
        "date": "2026-09-12T19:30:00Z",
        "competitions": [
            {
                "competitors": [
                    competitor("away", away, False),
                    competitor("home", home, completed),
                ],
                "status": {
                    "type": {
                        "description": "Final" if completed else "Scheduled",
                        "completed": completed,
                    }
                },
                "venue": {"fullName": "College Stadium"},
                "broadcasts": [{"names": ["ABC"]}],
            }
        ],
    }


def test_ncaaf_scoreboard_keeps_games_involving_major_conferences() -> None:
    payload = {
        "events": [
            _event("1", ("10", "Penn State", "5", 4), ("20", "Temple", "151", 99)),
            _event("2", ("30", "Army", "18", 99), ("40", "Navy", "18", 99)),
        ]
    }

    games = NCAAFEditionGenerator._games(payload, {})
    major = [game for game in games if game["major_conference"]]

    assert [game["id"] for game in major] == ["1"]
    assert major[0]["away"]["conference"] == "Big Ten"
    assert major[0]["away"]["rank"] == 4
    assert major[0]["home"]["rank"] == 0


def test_ncaaf_week_is_resolved_from_calendar_on_a_day_without_games() -> None:
    payload = {
        "leagues": [
            {
                "season": {"year": 2026, "type": {"id": "2", "name": "Regular Season"}},
                "calendar": [
                    {
                        "value": "2",
                        "entries": [
                            {
                                "label": "Week 2",
                                "detail": "Sep 8-13",
                                "value": "2",
                                "startDate": "2026-09-08T07:00Z",
                                "endDate": "2026-09-14T06:59Z",
                            }
                        ],
                    }
                ],
            }
        ],
    }

    week = NCAAFEditionGenerator._week_context(payload, date(2026, 9, 9))

    assert week["number"] == "2"
    assert week["label"] == "Week 2"
    assert week["detail"] == "Sep 8-13"


def test_ncaaf_major_conference_standings_are_selected_in_display_order() -> None:
    def conference(group_id: str, name: str) -> dict:
        return {
            "id": group_id,
            "name": name,
            "standings": {
                "entries": [
                    {
                        "team": {"location": f"{name} Team", "rank": 8},
                        "stats": [
                            {"name": "overall", "displayValue": "2-0"},
                            {"name": "streak", "displayValue": "W2"},
                            {"name": "leagueRecord", "displayValue": "1-0"},
                        ],
                    }
                ]
            },
        }

    payload = {
        "children": [
            conference("8", "Southeastern Conference"),
            conference("2", "American Conference"),
            conference("1", "Atlantic Coast Conference"),
        ]
    }

    groups = NCAAFEditionGenerator._conference_standings(payload)

    assert [group["name"] for group in groups] == ["ACC", "SEC"]
    assert groups[0]["rows"][0] == {
        "rank": 8,
        "team": "Atlantic Coast Conference Team",
        "conference": "1-0",
        "overall": "2-0",
        "streak": "W2",
    }


def test_ncaaf_ap_poll_and_lead_story_are_self_contained() -> None:
    payload = {
        "rankings": [
            {
                "name": "AP Top 25",
                "ranks": [
                    {
                        "current": 1,
                        "points": 1500,
                        "recordSummary": "2-0",
                        "team": {"id": "99", "location": "Penn State"},
                    }
                ],
            }
        ]
    }
    ranking_map, poll = NCAAFEditionGenerator._rankings(payload)
    games = NCAAFEditionGenerator._games(
        {
            "events": [
                _event(
                    "1", ("10", "Opponent", "1", 10), ("99", "Penn State", "5", 1), completed=True
                )
            ]
        },
        ranking_map,
    )

    assert ranking_map == {"99": 1}
    assert poll[0]["team"] == "Penn State"
    assert NCAAFEditionGenerator._lead_story(games)["headline"].startswith("No. 1 Penn State")


def test_sports_tabs_are_labeled_mlb_nfl_and_ncaaf() -> None:
    template = Path("templates/sections/sport-tabs.html.j2").read_text()
    assert ">MLB<" in template
    assert ">NFL<" in template
    assert ">NCAAF<" in template


def test_ncaaf_template_has_major_conference_tabs() -> None:
    template = Path("templates/ncaaf.html.j2").read_text()
    assert "Major-Conference Scoreboard" in template
    assert "AP Top 25" in template
    assert "Major-Conference Standings" in template
    assert 'data-tablist-id="ncaaf-conferences"' in template

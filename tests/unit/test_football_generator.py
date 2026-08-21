from datetime import date

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

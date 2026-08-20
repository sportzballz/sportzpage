from datetime import date

from src.collectors.odds import OddsCollector


def test_builds_date_specific_espn_url():
    collector = OddsCollector(date(2026, 8, 21))
    assert "dates=20260821" in collector.source_url


def test_parses_moneylines_and_total_without_total_prices():
    payload = {
        "events": [{
            "competitions": [{
                "competitors": [
                    {"homeAway": "away", "team": {"abbreviation": "ARI"}},
                    {"homeAway": "home", "team": {"abbreviation": "CHW"}},
                ],
                "odds": [{
                    "provider": {"displayName": "DraftKings"},
                    "overUnder": 8.5,
                    "moneyline": {
                        "away": {"close": {"odds": "+125"}},
                        "home": {"close": {"odds": "-145"}},
                    },
                    "total": {
                        "over": {"close": {"odds": "-110"}},
                        "under": {"close": {"odds": "-110"}},
                    },
                }],
            }],
        }],
    }

    assert OddsCollector.parse(payload) == [{
        "away_abbr": "AZ",
        "home_abbr": "CWS",
        "away_moneyline": 125,
        "home_moneyline": -145,
        "run_total": 8.5,
        "provider": "DraftKings",
    }]


def test_parses_in_progress_game_pickcenter_fallback():
    competition = {
        "competitors": [
            {"homeAway": "away", "team": {"abbreviation": "STL"}},
            {"homeAway": "home", "team": {"abbreviation": "CIN"}},
        ]
    }
    payload = {
        "pickcenter": [{
            "provider": {"name": "DraftKings"},
            "overUnder": 9.0,
            "awayTeamOdds": {"moneyLine": -110},
            "homeTeamOdds": {"moneyLine": 103},
            "overOdds": -102,
            "underOdds": -118,
        }]
    }

    assert OddsCollector.parse_pickcenter(payload, competition) == {
        "away_abbr": "STL",
        "home_abbr": "CIN",
        "away_moneyline": -110,
        "home_moneyline": 103,
        "run_total": 9.0,
        "provider": "DraftKings",
    }

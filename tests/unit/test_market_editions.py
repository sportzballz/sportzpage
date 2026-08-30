from src.market_editions import marketize_baseball, marketize_football
from src.markets import MARKETS_BY_SLUG
from tests.fixtures.builders import build_full_slate_edition


def test_market_configuration_covers_requested_launch_cities() -> None:
    assert set(MARKETS_BY_SLUG) == {
        "philadelphia",
        "boston",
        "new-york",
        "los-angeles",
        "chicago",
    }
    assert MARKETS_BY_SLUG["new-york"].baseball_teams == ("NYY", "NYM")
    assert MARKETS_BY_SLUG["los-angeles"].football_teams == ("LAR", "LAC")


def test_baseball_market_promotes_local_recap_and_sets_metadata() -> None:
    edition = build_full_slate_edition()

    chicago = marketize_baseball(edition, MARKETS_BY_SLUG["chicago"])

    assert chicago.edition.market_slug == "chicago"
    assert chicago.edition.market_label == "Chicago"
    assert chicago.edition.market_teams == ["CHC", "CWS"]
    assert chicago.lead_story is not None
    assert "Cubs" in chicago.lead_story.headline
    assert edition.edition.market_slug == "philadelphia"


def test_football_market_promotes_completed_local_game() -> None:
    page = {
        "lead": {"headline": "National lead"},
        "scoreboard": [
            {
                "id": "1",
                "completed": True,
                "status": "Final",
                "venue": "MetLife Stadium",
                "recap_url": "https://example.com/1",
                "away": {"abbr": "DAL", "name": "Dallas Cowboys", "score": "17", "winner": False},
                "home": {"abbr": "NYG", "name": "New York Giants", "score": "24", "winner": True},
            }
        ],
    }

    localized = marketize_football(page, MARKETS_BY_SLUG["new-york"])

    assert localized["market_slug"] == "new-york"
    assert localized["market_teams"] == ["NYG", "NYJ"]
    assert localized["canonical_path"] == "/editions/new-york/football/"
    assert localized["lead"]["headline"].startswith("New York Giants")
    assert "New York edition" in localized["lead"]["paragraphs"][2]

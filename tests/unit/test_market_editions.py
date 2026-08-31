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
        "dallas",
    }
    assert MARKETS_BY_SLUG["new-york"].baseball_teams == ("NYY", "NYM")
    assert MARKETS_BY_SLUG["los-angeles"].football_teams == ("LAR", "LAC")
    assert MARKETS_BY_SLUG["dallas"].baseball_teams == ("TEX",)
    assert MARKETS_BY_SLUG["dallas"].football_teams == ("DAL",)


def test_baseball_market_promotes_local_recap_and_sets_metadata() -> None:
    edition = build_full_slate_edition()

    chicago = marketize_baseball(edition, MARKETS_BY_SLUG["chicago"])

    assert chicago.edition.market_slug == "chicago"
    assert chicago.edition.market_label == "Chicago"
    assert chicago.edition.market_teams == ["CHC", "CWS"]
    assert chicago.lead_story is not None
    assert "Cubs" in chicago.lead_story.headline
    assert edition.edition.market_slug == "philadelphia"


def test_baseball_market_uses_full_ai_headline_rewrite() -> None:
    edition = build_full_slate_edition()
    local_recap = next(recap for recap in edition.game_recaps if "CHC" in recap.teams)
    rewritten = local_recap.model_copy(
        update={
            "headline": "OpenAI rewrites the Chicago headline",
            "paragraphs": ["First.", "Second.", "Third."],
            "ai_generated": True,
        }
    )

    chicago = marketize_baseball(edition, MARKETS_BY_SLUG["chicago"], rewritten)

    assert chicago.lead_story is not None
    assert chicago.lead_story.headline == "OpenAI rewrites the Chicago headline"
    assert chicago.lead_story.paragraphs == ["First.", "Second.", "Third."]
    assert chicago.lead_story.ai_generated is True


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


def test_football_market_uses_full_ai_headline_rewrite() -> None:
    page = {
        "lead": {"headline": "National lead"},
        "scoreboard": [
            {
                "id": "1",
                "completed": True,
                "away": {"abbr": "DAL"},
                "home": {"abbr": "NYG"},
            }
        ],
    }
    rewritten = {
        "headline": "OpenAI rewrites the New York headline",
        "deck": "A rewritten deck.",
        "paragraphs": ["First.", "Second.", "Third."],
        "ai_generated": True,
    }

    localized = marketize_football(page, MARKETS_BY_SLUG["new-york"], rewritten)

    assert localized["lead"] == rewritten
    assert localized["lead"] is not rewritten

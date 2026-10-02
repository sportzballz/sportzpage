from src.market_editions import (
    baseball_headline_game,
    marketize_baseball,
    marketize_football,
    previous_baseball_lead,
)
from src.markets import MARKETS_BY_SLUG
from src.models.postseason import Postseason, PostseasonSeries
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


def test_eliminated_market_team_yields_headline_to_another_playoff_game() -> None:
    edition = build_full_slate_edition()
    edition.edition.date = "2026-07-14"
    for game in edition.games:
        game.game_type = "F"
    edition.postseason = Postseason(
        series=[
            PostseasonSeries(
                key="NL Wild Card:CHC:MIL",
                round_name="NL Wild Card",
                league="NL",
                away_team="MIL",
                home_team="CHC",
                away_wins=2,
                home_wins=0,
                wins_required=2,
                status="MIL won 2–0",
            ),
            PostseasonSeries(
                key="AL Wild Card:BOS:NYY",
                round_name="AL Wild Card",
                league="AL",
                away_team="BOS",
                home_team="NYY",
                away_wins=0,
                home_wins=1,
                wins_required=2,
                status="NYY leads 1–0",
            ),
        ]
    )

    selected = baseball_headline_game(edition, MARKETS_BY_SLUG["chicago"])
    localized = marketize_baseball(edition, MARKETS_BY_SLUG["chicago"])

    assert selected is not None
    assert selected.game_id == 748293
    assert localized.lead_story is not None
    assert localized.lead_story.teams == ["NYY", "BOS"]


def test_elimination_game_yields_to_latest_other_completed_playoff_game() -> None:
    edition = build_full_slate_edition()
    edition.edition.date = "2026-07-14"
    for game in edition.games:
        game.game_type = "F"
        game.game_date = "2026-07-12"
    phillies_game = next(game for game in edition.games if game.game_id == 748295)
    phillies_game.game_date = "2026-07-13"
    yankees_game = next(game for game in edition.games if game.game_id == 748293)
    edition.postseason = Postseason(
        games=[phillies_game, yankees_game],
        series=[
            PostseasonSeries(
                key="NL Wild Card:ATL:PHI",
                round_name="NL Wild Card",
                league="NL",
                away_team="ATL",
                home_team="PHI",
                away_wins=2,
                home_wins=1,
                wins_required=2,
                status="ATL won 2–1",
            )
        ],
    )

    selected = baseball_headline_game(edition, MARKETS_BY_SLUG["philadelphia"])

    assert selected is not None
    assert "PHI" not in {selected.away.team_abbr, selected.home.team_abbr}
    assert selected.game_date == "2026-07-12"


def test_postseason_off_day_reuses_previous_market_lead(tmp_path) -> None:
    edition = build_full_slate_edition()
    edition.edition.date = "2026-07-14"
    for game in edition.games:
        game.game_type = "F"
        game.game_date = "2026-07-12"
    edition.postseason = Postseason(
        series=[
            PostseasonSeries(
                key="AL Wild Card:BOS:NYY",
                round_name="AL Wild Card",
                league="AL",
                away_team="BOS",
                home_team="NYY",
                wins_required=2,
                status="Series tied 0–0",
            )
        ]
    )
    previous = build_full_slate_edition()
    previous.lead_story.headline = "Yesterday's playoff headline"
    previous_path = tmp_path / "philadelphia-edition.json"
    previous_path.write_text(previous.model_dump_json(), encoding="utf-8")

    prior_lead = previous_baseball_lead(previous_path)
    localized = marketize_baseball(
        edition,
        MARKETS_BY_SLUG["philadelphia"],
        previous_lead=prior_lead,
    )

    assert baseball_headline_game(edition, MARKETS_BY_SLUG["philadelphia"]) is None
    assert localized.lead_story is not None
    assert localized.lead_story.headline == "Yesterday's playoff headline"


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

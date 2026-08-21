# tests/unit/test_editorial.py
from __future__ import annotations

import pytest

from src.editorial.engine import (
    NL_EAST_TEAMS,
    EditorialEngine,
    prioritize_division_team,
    prioritize_primary_team,
)
from src.editorial.fallback import generate_fallback_recap
from src.editorial.scoring import ScoringContext, ScoringWeights, score_game
from src.models.game import Game, GameStatus, Pitcher, TeamGameLine
from src.models.story import GameRecap

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_game(
    game_id: int = 1,
    home_runs: int = 5,
    away_runs: int = 3,
    tags: list[str] | None = None,
    winning_pitcher: Pitcher | None = None,
    losing_pitcher: Pitcher | None = None,
    save_pitcher: Pitcher | None = None,
) -> Game:
    return Game(
        game_id=game_id,
        game_date="2026-07-13",
        status=GameStatus.final,
        home=TeamGameLine(
            team_id=147,
            team_abbr="NYY",
            team_name="New York Yankees",
            runs=home_runs,
        ),
        away=TeamGameLine(
            team_id=111,
            team_abbr="BOS",
            team_name="Boston Red Sox",
            runs=away_runs,
        ),
        tags=tags or [],
        winning_pitcher=winning_pitcher,
        losing_pitcher=losing_pitcher,
        save_pitcher=save_pitcher,
    )


def _default_weights() -> ScoringWeights:
    return ScoringWeights()


def _zero_context(**overrides) -> ScoringContext:
    return ScoringContext(**overrides)


# ---------------------------------------------------------------------------
# score_game tests
# ---------------------------------------------------------------------------


def test_score_game_playoff_weight():
    """is_postseason=True, all else 0 → score equals playoff_weight."""
    weights = _default_weights()
    context = _zero_context(is_postseason=True)
    game = _make_game()
    result = score_game(game, context, weights, {})
    assert result == weights.playoff_weight


def test_score_game_historic_weight():
    """has_historic_performance=True, all else 0 → score equals historic_weight."""
    weights = _default_weights()
    context = _zero_context(has_historic_performance=True)
    game = _make_game()
    result = score_game(game, context, weights, {})
    assert result == weights.historic_weight


def test_score_game_manual_override():
    """Manual override for game_id=999 returns 10.0 regardless of context."""
    weights = _default_weights()
    context = _zero_context(
        is_postseason=True, has_historic_performance=True, performance_score=5.0
    )
    game = _make_game(game_id=999)
    result = score_game(game, context, weights, {999: 10.0})
    assert result == 10.0


def test_score_game_manual_override_zero():
    """Manual override of 0.0 takes precedence even when postseason=True."""
    weights = _default_weights()
    context = _zero_context(is_postseason=True)
    game = _make_game(game_id=999)
    result = score_game(game, context, weights, {999: 0.0})
    assert result == 0.0


def test_score_game_zero_context():
    """All context flags False/0 → score = 0.0."""
    weights = _default_weights()
    context = _zero_context()
    game = _make_game()
    result = score_game(game, context, weights, {})
    assert result == 0.0


def test_phillies_game_is_always_prioritized_for_front_page():
    national_game = _make_game(game_id=1)
    phillies_game = _make_game(game_id=2)
    phillies_game.away = TeamGameLine(
        team_id=143,
        team_abbr="PHI",
        team_name="Philadelphia Phillies",
        runs=2,
    )

    ordered = prioritize_primary_team(
        [(national_game, 10.0), (phillies_game, 1.0)], "PHI"
    )

    assert ordered[0][0].game_id == 2
    assert ordered[1][0].game_id == 1


def test_nl_east_game_is_prioritized_when_phillies_did_not_play():
    national_game = _make_game(game_id=1)
    nationals_game = _make_game(game_id=2)
    nationals_game.away = TeamGameLine(
        team_id=120,
        team_abbr="WSH",
        team_name="Washington Nationals",
        runs=3,
    )

    ordered = prioritize_division_team(
        [(national_game, 10.0), (nationals_game, 1.0)], NL_EAST_TEAMS
    )

    assert ordered[0][0].game_id == 2
    assert ordered[1][0].game_id == 1


def test_lead_story_is_three_to_five_paragraphs():
    game = _make_game()
    recap = generate_fallback_recap(game)

    paragraphs = EditorialEngine._lead_paragraphs(recap, game)

    assert 3 <= len(paragraphs) <= 5


@pytest.mark.asyncio
async def test_secondary_front_page_recap_uses_short_llm_mode() -> None:
    game = _make_game()
    generated = generate_fallback_recap(game).model_copy(update={"ai_generated": True})

    class FakeStoryService:
        short_requested = False

        async def generate(self, requested_game: Game, *, short: bool = False) -> GameRecap:
            assert requested_game is game
            self.short_requested = short
            return generated

    service = FakeStoryService()
    engine = EditorialEngine(
        scoring_weights=_default_weights(),
        manual_overrides={},
        suppress_story_ids=[],
        large_market_teams=set(),
        lead_story_service=service,  # type: ignore[arg-type]
    )

    result = await engine._generate_secondary_recap(game)

    assert service.short_requested is True
    assert result.ai_generated is True


def test_phillies_fallback_headline_covers_scheduled_game():
    game = _make_game(game_id=3)
    game.status = GameStatus.scheduled
    game.away = TeamGameLine(
        team_id=143,
        team_abbr="PHI",
        team_name="Philadelphia Phillies",
        runs=None,
    )
    game.home.runs = None
    game.game_time_et = "7:05 PM"

    engine = EditorialEngine(
        scoring_weights=_default_weights(),
        manual_overrides={},
        suppress_story_ids=[],
        large_market_teams=set(),
    )
    story = engine._primary_team_fallback(game)

    assert story.headline.startswith("Phillies")
    assert "New York Yankees" in story.headline
    assert story.story_type.value == "lead"


# ---------------------------------------------------------------------------
# generate_fallback_recap tests
# ---------------------------------------------------------------------------


def test_generate_fallback_recap_walk_off():
    """Walk-off tag: headline contains winner name and score, body contains 'walk-off'."""
    game = _make_game(home_runs=4, away_runs=3, tags=["walk-off"])
    recap = generate_fallback_recap(game)
    assert "New York Yankees" in recap.headline
    assert "4" in recap.headline
    body = " ".join(recap.paragraphs)
    assert "walk-off" in body.lower()


def test_generate_fallback_recap_extra_innings():
    """Extra-inning tag: body contains 'extra innings'."""
    game = _make_game(home_runs=6, away_runs=5, tags=["extra-inning"])
    recap = generate_fallback_recap(game)
    body = " ".join(recap.paragraphs)
    assert "extra innings" in body.lower()


def test_generate_fallback_recap_no_ai_flag():
    """Returned recap has ai_generated=False."""
    game = _make_game()
    recap = generate_fallback_recap(game)
    assert recap.ai_generated is False


def test_generate_fallback_recap_facts_used_populated():
    """Returned recap has non-empty facts_used."""
    game = _make_game()
    recap = generate_fallback_recap(game)
    assert len(recap.facts_used) > 0

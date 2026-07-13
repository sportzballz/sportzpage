# src/editorial/scoring.py
from __future__ import annotations
import logging
from dataclasses import dataclass, field
from src.models.game import Game

logger = logging.getLogger(__name__)


@dataclass
class ScoringWeights:
    """Weights for the lead-story scoring model. All values are floats."""

    playoff_weight: float = 3.0
    historic_weight: float = 2.5
    performance_weight: float = 2.0
    game_drama_weight: float = 1.5
    national_interest_weight: float = 1.0
    recency_weight: float = 0.5


@dataclass
class ScoringContext:
    """Contextual flags that inform scoring for a single game."""

    is_postseason: bool = False
    has_historic_performance: bool = False
    performance_score: float = 0.0
    drama_score: float = 0.0
    is_nationally_televised: bool = False
    is_large_market: bool = False
    recency_bonus: float = 0.0


def score_game(
    game: Game,
    context: ScoringContext,
    weights: ScoringWeights,
    manual_overrides: dict[int, float],
) -> float:
    """
    Compute the lead-story score for a game.
    If a manual override is present for this game_id, it takes precedence.
    """
    if game.game_id in manual_overrides:
        score = manual_overrides[game.game_id]
        logger.info("game %d: manual override score %.2f", game.game_id, score)
        return score

    score = (
        (weights.playoff_weight if context.is_postseason else 0.0)
        + (weights.historic_weight if context.has_historic_performance else 0.0)
        + weights.performance_weight * context.performance_score
        + weights.game_drama_weight * context.drama_score
        + (
            weights.national_interest_weight
            if (context.is_nationally_televised or context.is_large_market)
            else 0.0
        )
        + weights.recency_weight * context.recency_bonus
    )
    logger.debug("game %d score: %.3f", game.game_id, score)
    return score

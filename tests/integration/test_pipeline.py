# tests/integration/test_pipeline.py
"""Integration tests for normalization and validation pipeline stages."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from src.models.edition import Edition, EditionMetadata, GenerationMetadata
from src.models.game import Game, GameStatus, TeamGameLine
from src.models.story import GameRecap, StoryType
from src.normalization.normalizer import NormalizedData, Normalizer
from src.validation.validator import ContentValidator

_NOW = datetime.now(timezone.utc)

# ---------------------------------------------------------------------------
# Minimal MLB Stats API schedule fixture
# ---------------------------------------------------------------------------

_SCHEDULE_FIXTURE: dict = {
    "dates": [
        {
            "date": "2026-07-13",
            "games": [
                {
                    "gamePk": 748293,
                    "gameDate": "2026-07-13T23:05:00Z",
                    "status": {"detailedState": "Final"},
                    "teams": {
                        "home": {
                            "team": {"id": 147, "name": "New York Yankees", "abbreviation": "NYY"},
                            "score": 5,
                            "isWinner": True,
                        },
                        "away": {
                            "team": {"id": 111, "name": "Boston Red Sox", "abbreviation": "BOS"},
                            "score": 3,
                            "isWinner": False,
                        },
                    },
                    "linescore": {
                        "currentInning": 9,
                        "inningState": "Bottom",
                        "teams": {
                            "home": {"runs": 5, "hits": 9, "errors": 0},
                            "away": {"runs": 3, "hits": 7, "errors": 1},
                        },
                        "innings": [],
                    },
                    "venue": {"id": 3313, "name": "Yankee Stadium", "location": {"city": "Bronx"}},
                    "broadcasts": [],
                    "doubleHeader": "N",
                    "gameNumber": 1,
                }
            ],
        }
    ]
}


# ---------------------------------------------------------------------------
# Test 1: Normalization to NormalizedData round-trip
# ---------------------------------------------------------------------------


def test_normalization_round_trip() -> None:
    """Normalizer produces a NormalizedData with games; model survives a JSON round-trip."""
    raw = {"schedule": _SCHEDULE_FIXTURE}
    normalizer = Normalizer()

    normalized = normalizer.normalize(raw)

    assert isinstance(normalized, NormalizedData)
    assert len(normalized.games) == 1

    game = normalized.games[0]
    assert game.game_id == 748293
    assert game.status == GameStatus.final
    assert game.home.team_abbr == "NYY"
    assert game.home.runs == 5
    assert game.away.team_abbr == "BOS"
    assert game.away.runs == 3

    # Round-trip through JSON
    serialized = normalized.model_dump_json()
    restored = NormalizedData.model_validate_json(serialized)
    assert len(restored.games) == 1
    assert restored.games[0].game_id == 748293


# ---------------------------------------------------------------------------
# Test 2: Validator rejects a GameRecap with a wrong final_score
# ---------------------------------------------------------------------------


def test_validator_rejects_bad_final_score() -> None:
    """ContentValidator must report an error when a GameRecap's final_score doesn't match game data."""
    game = Game(
        game_id=748293,
        game_date="2026-07-13",
        status=GameStatus.final,
        home=TeamGameLine(
            team_id=147,
            team_abbr="NYY",
            team_name="New York Yankees",
            runs=5,
        ),
        away=TeamGameLine(
            team_id=111,
            team_abbr="BOS",
            team_name="Boston Red Sox",
            runs=3,
        ),
    )

    # Intentionally wrong score (swapped runs)
    bad_recap = GameRecap(
        game_id=748293,
        final_score="BOS 5, NYY 3",  # wrong — NYY won 5-3
        headline="Red Sox Upset Yankees in Bronx",
        deck="A surprising result at Yankee Stadium.",
        paragraphs=["The Red Sox defeated the Yankees 5-3."],
        story_type=StoryType.game_recap,
    )

    edition = Edition(
        edition=EditionMetadata(
            id="2026-07-13-2300",
            type="final",
            date="2026-07-13",
            generated_at=_NOW,
            data_current_through=_NOW,
            status="draft",
        ),
        games=[game],
        game_recaps=[bad_recap],
        generation_metadata=GenerationMetadata(pipeline_version="0.1.0"),
    )

    validator = ContentValidator()
    report = validator.validate_edition(edition)

    assert report.has_errors, "Expected validation errors but found none"
    assert any("final_score" in e or "748293" in e for e in report.errors), (
        f"Expected score mismatch error, got: {report.errors}"
    )

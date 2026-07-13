# tests/unit/test_validator.py
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models.edition import Edition, EditionMetadata, GenerationMetadata
from src.models.game import Game, GameStatus, TeamGameLine, Pitcher
from src.models.injuries import Injury, InjuryConfidence, RosterStatus
from src.models.story import GameRecap, Story, StoryType
from src.validation.validator import ContentValidator


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(timezone.utc)


def _edition_metadata() -> EditionMetadata:
    return EditionMetadata(
        id="2026-07-13-0600",
        type="morning",
        date="2026-07-13",
        generated_at=_NOW,
        data_current_through=_NOW,
        status="draft",
    )


def _make_game(
    game_id: int = 1,
    home_abbr: str = "NYY",
    home_name: str = "New York Yankees",
    home_runs: int = 5,
    away_abbr: str = "BOS",
    away_name: str = "Boston Red Sox",
    away_runs: int = 3,
) -> Game:
    return Game(
        game_id=game_id,
        game_date="2026-07-13",
        status=GameStatus.final,
        home=TeamGameLine(team_id=147, team_abbr=home_abbr, team_name=home_name, runs=home_runs),
        away=TeamGameLine(team_id=111, team_abbr=away_abbr, team_name=away_name, runs=away_runs),
    )


def _make_recap(
    game_id: int = 1,
    final_score: str = "NYY 5, BOS 3",
    headline: str = "Yankees top Red Sox",
    paragraphs: list[str] | None = None,
) -> GameRecap:
    return GameRecap(
        game_id=game_id,
        final_score=final_score,
        headline=headline,
        deck="Final from the Bronx.",
        paragraphs=paragraphs or ["The Yankees defeated the Red Sox 5–3."],
        story_type=StoryType.game_recap,
        ai_generated=False,
    )


def _minimal_edition(game: Game | None = None, recap: GameRecap | None = None) -> Edition:
    g = game or _make_game()
    r = recap or _make_recap()
    return Edition(
        edition=_edition_metadata(),
        games=[g],
        game_recaps=[r],
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_valid_edition_passes():
    """Minimal valid edition with matching recap score → no errors."""
    edition = _minimal_edition()
    validator = ContentValidator()
    report = validator.validate_edition(edition)
    assert not report.has_errors, report.errors


def test_score_mismatch_error():
    """GameRecap.final_score doesn't match game data → error in report."""
    game = _make_game(home_runs=5, away_runs=3)
    recap = _make_recap(final_score="NYY 9, BOS 2")  # wrong
    edition = _minimal_edition(game=game, recap=recap)
    report = ContentValidator().validate_edition(edition)
    assert report.has_errors
    assert any("final_score" in e or "doesn't match" in e for e in report.errors)


def test_missing_game_id_error():
    """GameRecap references a game_id not in edition.games → error."""
    game = _make_game(game_id=1)
    recap = _make_recap(game_id=99999, final_score="NYY 5, BOS 3")
    edition = Edition(
        edition=_edition_metadata(),
        games=[game],
        game_recaps=[recap],
    )
    report = ContentValidator().validate_edition(edition)
    assert report.has_errors
    assert any("99999" in e for e in report.errors)


def test_forbidden_phrase_error():
    """Story paragraph contains 'according to sources' → error."""
    game = _make_game()
    recap = _make_recap(
        paragraphs=["According to sources, the team won the game 5–3."],
    )
    edition = _minimal_edition(game=game, recap=recap)
    report = ContentValidator().validate_edition(edition)
    assert report.has_errors
    assert any("according to sources" in e for e in report.errors)


def test_empty_headline_error():
    """Story with empty headline → error."""
    game = _make_game()
    recap = _make_recap(headline="")
    edition = _minimal_edition(game=game, recap=recap)
    report = ContentValidator().validate_edition(edition)
    assert report.has_errors
    assert any("empty headline" in e for e in report.errors)


def test_empty_paragraphs_error():
    """Story with paragraphs=[''] → error."""
    game = _make_game()
    recap = _make_recap(paragraphs=[""])
    edition = _minimal_edition(game=game, recap=recap)
    report = ContentValidator().validate_edition(edition)
    assert report.has_errors
    assert any("empty body" in e for e in report.errors)


def test_duplicate_text_warning():
    """Two stories with identical long paragraphs → warning in report."""
    long_para = "A" * 100  # well above the 50-char threshold
    game1 = _make_game(game_id=1)
    game2 = _make_game(
        game_id=2,
        home_abbr="LAD",
        home_name="Los Angeles Dodgers",
        away_abbr="SF",
        away_name="San Francisco Giants",
    )
    recap1 = _make_recap(
        game_id=1, final_score="NYY 5, BOS 3", headline="Game One", paragraphs=[long_para]
    )
    recap2 = GameRecap(
        game_id=2,
        final_score="LAD 5, SF 3",
        headline="Game Two",
        deck="Another game.",
        paragraphs=[long_para],
        story_type=StoryType.game_recap,
        ai_generated=False,
    )
    edition = Edition(
        edition=_edition_metadata(),
        games=[game1, game2],
        game_recaps=[recap1, recap2],
    )
    report = ContentValidator().validate_edition(edition)
    assert any("Duplicate text" in w for w in report.warnings)


def test_speculative_injury_warning():
    """Speculative injury with expected_return set → warning."""
    injury = Injury(
        player_id=1234,
        player_name="John Doe",
        team_abbr="NYY",
        injury_description="right hamstring strain",
        roster_status=RosterStatus.ten_day_il,
        confidence_level=InjuryConfidence.speculative,
        expected_return="next week",
    )
    edition = Edition(
        edition=_edition_metadata(),
        games=[],
        injuries=[injury],
    )
    report = ContentValidator().validate_edition(edition)
    assert any("speculative" in w for w in report.warnings)


def test_validate_edition_file_no_errors(tmp_path: Path):
    """Write a valid edition JSON to disk and validate via file path → no errors."""
    edition = _minimal_edition()
    edition_json = edition.model_dump(mode="json")
    p = tmp_path / "edition.json"
    p.write_text(json.dumps(edition_json))
    report = ContentValidator().validate_edition_file(p)
    assert not report.has_errors, report.errors

# tests/unit/test_models.py
"""Comprehensive unit tests for all SportzBallz domain models."""

from __future__ import annotations

import pytest
from datetime import date, datetime, timezone

from src.models.game import Game, GameStatus, Pitcher, TeamGameLine, LinescoreInning
from src.models.standings import StandingsRow, DivisionStandings, WildCardStandings, Standings
from src.models.leaders import LeaderEntry, LeagueLeaders
from src.models.story import Story, GameRecap, StoryType
from src.models.transactions import Transaction, TransactionType
from src.models.injuries import Injury, RosterStatus, InjuryConfidence
from src.models.history import HistoricalItem
from src.models.freshness import DataFreshness
from src.models.run import GenerationRun, RunStatus, PhaseStatus, RunPhase
from src.models.edition import Edition, EditionMetadata, GenerationMetadata

from pydantic import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_team_line(abbr: str = "NYY", team_id: int = 147) -> TeamGameLine:
    return TeamGameLine(team_id=team_id, team_abbr=abbr, team_name="New York Yankees")


def _make_game(**kwargs) -> Game:
    defaults = dict(
        game_id=748293,
        game_date="2026-07-13",
        status=GameStatus.final,
        home=_make_team_line("NYY", 147),
        away=_make_team_line("BOS", 111),
    )
    defaults.update(kwargs)
    return Game(**defaults)


def _make_pitcher(**kwargs) -> Pitcher:
    defaults = dict(player_id=543037, name="Gerrit Cole")
    defaults.update(kwargs)
    return Pitcher(**defaults)


def _make_standings_row(**kwargs) -> StandingsRow:
    defaults = dict(
        team_id=147,
        team_abbr="NYY",
        team_name="New York Yankees",
        wins=55,
        losses=35,
        pct=0.611,
        games_back=0.0,
        last_10="7-3",
        streak="W2",
        home_record="30-15",
        away_record="25-20",
        run_differential=42,
    )
    defaults.update(kwargs)
    return StandingsRow(**defaults)


def _make_story(**kwargs) -> Story:
    defaults = dict(
        headline="Yankees Win Again",
        deck="New York continues hot streak.",
        paragraphs=["The Yankees defeated the Red Sox 5-3 on Sunday."],
        story_type=StoryType.lead,
    )
    defaults.update(kwargs)
    return Story(**defaults)


def _make_edition_metadata(**kwargs) -> EditionMetadata:
    defaults = dict(
        id="2026-07-13-0600",
        type="morning",
        date="2026-07-13",
        generated_at=datetime(2026, 7, 13, 6, 0, 0, tzinfo=timezone.utc),
        data_current_through=datetime(2026, 7, 13, 5, 55, 0, tzinfo=timezone.utc),
        status="published",
    )
    defaults.update(kwargs)
    return EditionMetadata(**defaults)


def _make_edition(**kwargs) -> Edition:
    defaults = dict(edition=_make_edition_metadata())
    defaults.update(kwargs)
    return Edition(**defaults)


# ---------------------------------------------------------------------------
# 1. GameStatus enum values
# ---------------------------------------------------------------------------


class TestGameStatus:
    def test_all_values_present(self):
        values = {s.value for s in GameStatus}
        assert values == {"final", "in_progress", "scheduled", "postponed", "delayed", "suspended"}

    def test_is_str_enum(self):
        assert isinstance(GameStatus.final, str)
        assert GameStatus.final == "final"


# ---------------------------------------------------------------------------
# 2. Game model creation with all fields
# ---------------------------------------------------------------------------


class TestGameFullCreation:
    def test_full_game(self):
        pitcher = _make_pitcher(wins=10, losses=4, era=2.81, handedness="R")
        game = _make_game(
            game_time_et="7:05 PM",
            inning=9,
            inning_state="Bottom",
            linescore=[LinescoreInning(inning=1, away_runs=0, home_runs=1)],
            home_probable_pitcher=pitcher,
            away_probable_pitcher=pitcher,
            winning_pitcher=pitcher,
            losing_pitcher=pitcher,
            save_pitcher=pitcher,
            venue_name="Yankee Stadium",
            venue_city="Bronx, NY",
            tv_broadcasts=["YES", "NESN"],
            weather_description="Partly cloudy, 78°F",
            attendance=45000,
            time_of_game="3:12",
            is_doubleheader=True,
            doubleheader_game_num=1,
            tags=["walk-off"],
            series_description="ALDS Game 3",
            recap_anchor="recap-748293",
        )
        assert game.game_id == 748293
        assert game.status == GameStatus.final
        assert game.venue_name == "Yankee Stadium"
        assert game.is_doubleheader is True
        assert len(game.linescore) == 1
        assert game.winning_pitcher.name == "Gerrit Cole"


# ---------------------------------------------------------------------------
# 3. Game model with minimal required fields (defaults work)
# ---------------------------------------------------------------------------


class TestGameMinimalCreation:
    def test_minimal_game(self):
        game = _make_game()
        assert game.inning is None
        assert game.linescore == []
        assert game.tv_broadcasts == []
        assert game.tags == []
        assert game.is_doubleheader is False

    def test_status_enum_coercion(self):
        game = _make_game(status="scheduled")
        assert game.status == GameStatus.scheduled


# ---------------------------------------------------------------------------
# 4. Pitcher model with and without optional fields
# ---------------------------------------------------------------------------


class TestPitcher:
    def test_minimal_pitcher(self):
        p = _make_pitcher()
        assert p.handedness is None
        assert p.wins is None
        assert p.era is None
        assert p.status == "probable"

    def test_full_pitcher(self):
        p = _make_pitcher(handedness="L", status="confirmed", wins=12, losses=5, era=3.14)
        assert p.handedness == "L"
        assert p.era == 3.14

    def test_status_default(self):
        p = Pitcher(player_id=1, name="Test")
        assert p.status == "probable"


# ---------------------------------------------------------------------------
# 5. StandingsRow PCT and games_back validation
# ---------------------------------------------------------------------------


class TestStandingsRow:
    def test_pct_float(self):
        row = _make_standings_row(pct=0.611)
        assert row.pct == pytest.approx(0.611)

    def test_games_back_float(self):
        row = _make_standings_row(games_back=2.5)
        assert row.games_back == 2.5

    def test_games_back_string(self):
        # Some providers return "-" for the leader
        row = _make_standings_row(games_back="-")
        assert row.games_back == "-"

    def test_eliminated_default(self):
        row = _make_standings_row()
        assert row.eliminated is False

    def test_magic_number_none_default(self):
        row = _make_standings_row()
        assert row.magic_number is None


# ---------------------------------------------------------------------------
# 6. LeaderEntry rank ge=1 constraint
# ---------------------------------------------------------------------------


class TestLeaderEntry:
    def _make_entry(self, rank: int = 1) -> LeaderEntry:
        return LeaderEntry(
            rank=rank,
            player_id=543037,
            player_name="Gerrit Cole",
            team_abbr="NYY",
            position="SP",
            value="2.81",
            games_played=18,
            league="AL",
            qualified=True,
        )

    def test_valid_rank(self):
        entry = self._make_entry(rank=1)
        assert entry.rank == 1

    def test_rank_zero_raises(self):
        with pytest.raises(ValidationError):
            self._make_entry(rank=0)

    def test_rank_negative_raises(self):
        with pytest.raises(ValidationError):
            self._make_entry(rank=-1)

    def test_rank_large(self):
        entry = self._make_entry(rank=50)
        assert entry.rank == 50


# ---------------------------------------------------------------------------
# 7. Story paragraphs min_length=1 constraint
# ---------------------------------------------------------------------------


class TestStory:
    def test_empty_paragraphs_raises(self):
        with pytest.raises(ValidationError):
            Story(
                headline="Test",
                deck="Test deck.",
                paragraphs=[],
                story_type=StoryType.editorial,
            )

    def test_single_paragraph_ok(self):
        story = _make_story(paragraphs=["Single paragraph."])
        assert len(story.paragraphs) == 1

    def test_defaults(self):
        story = _make_story()
        assert story.byline == "SportzBallz Staff"
        assert story.ai_generated is True
        assert story.teams == []
        assert story.facts_used == []


# ---------------------------------------------------------------------------
# 8. GameRecap inherits from Story
# ---------------------------------------------------------------------------


class TestGameRecap:
    def _make_recap(self, **kwargs) -> GameRecap:
        defaults = dict(
            headline="Yankees Top Red Sox in Extra Innings",
            deck="Walk-off single in the 11th.",
            paragraphs=["The Yankees won 4-3 in extra innings."],
            story_type=StoryType.game_recap,
            game_id=748293,
            final_score="NYY 4, BOS 3",
        )
        defaults.update(kwargs)
        return GameRecap(**defaults)

    def test_is_story_subclass(self):
        recap = self._make_recap()
        assert isinstance(recap, Story)

    def test_game_id_required(self):
        with pytest.raises(ValidationError):
            GameRecap(
                headline="Test",
                deck="Deck.",
                paragraphs=["Para."],
                story_type=StoryType.game_recap,
                final_score="NYY 5, BOS 3",
                # game_id omitted
            )

    def test_final_score_present(self):
        recap = self._make_recap()
        assert recap.final_score == "NYY 4, BOS 3"

    def test_tags_default_empty(self):
        recap = self._make_recap()
        assert recap.tags == []

    def test_winning_pitcher_optional(self):
        recap = self._make_recap(winning_pitcher=_make_pitcher())
        assert recap.winning_pitcher.name == "Gerrit Cole"


# ---------------------------------------------------------------------------
# 9. TransactionType values
# ---------------------------------------------------------------------------


class TestTransactionType:
    def test_all_values(self):
        expected = {
            "trade",
            "dfa",
            "released",
            "signed",
            "optioned",
            "recalled",
            "injury",
            "placed_on_il",
            "activated",
            "claimed",
            "retired",
            "other",
        }
        actual = {t.value for t in TransactionType}
        assert actual == expected

    def test_is_str_enum(self):
        assert isinstance(TransactionType.trade, str)


# ---------------------------------------------------------------------------
# 10. Injury.expected_return can be None (never invented)
# ---------------------------------------------------------------------------


class TestInjury:
    def _make_injury(self, **kwargs) -> Injury:
        defaults = dict(
            player_id=543037,
            player_name="Gerrit Cole",
            team_abbr="NYY",
            injury_description="Right elbow inflammation",
            roster_status=RosterStatus.fifteen_day_il,
            confidence_level=InjuryConfidence.confirmed,
        )
        defaults.update(kwargs)
        return Injury(**defaults)

    def test_expected_return_defaults_none(self):
        injury = self._make_injury()
        assert injury.expected_return is None

    def test_expected_return_accepts_string(self):
        injury = self._make_injury(expected_return="mid-August")
        assert injury.expected_return == "mid-August"

    def test_date_of_injury_optional(self):
        injury = self._make_injury(date_of_injury=date(2026, 7, 1))
        assert injury.date_of_injury == date(2026, 7, 1)

    def test_roster_status_enum(self):
        injury = self._make_injury()
        assert injury.roster_status == RosterStatus.fifteen_day_il


# ---------------------------------------------------------------------------
# 11. HistoricalItem year ge=1839 constraint
# ---------------------------------------------------------------------------


class TestHistoricalItem:
    def _make_item(self, year: int = 1969) -> HistoricalItem:
        return HistoricalItem(
            year=year,
            headline="Mets Win World Series",
            description="The 'Miracle Mets' defeated the Baltimore Orioles in five games.",
            source="Baseball Reference",
        )

    def test_valid_year(self):
        item = self._make_item(year=1927)
        assert item.year == 1927

    def test_year_boundary_1839(self):
        item = self._make_item(year=1839)
        assert item.year == 1839

    def test_year_too_early_raises(self):
        with pytest.raises(ValidationError):
            self._make_item(year=1838)

    def test_verified_default_true(self):
        item = self._make_item()
        assert item.verified is True

    def test_teams_players_default_empty(self):
        item = self._make_item()
        assert item.teams == []
        assert item.players == []


# ---------------------------------------------------------------------------
# 12. Edition model_validate round-trip
# ---------------------------------------------------------------------------


class TestEditionRoundTrip:
    def test_round_trip_minimal(self):
        edition = _make_edition()
        data = edition.model_dump(mode="json")
        restored = Edition.model_validate(data)
        assert restored.edition.id == edition.edition.id
        assert restored.edition.type == edition.edition.type
        assert restored.games == []

    def test_round_trip_with_games(self):
        game = _make_game(
            home=TeamGameLine(
                team_id=147, team_abbr="NYY", team_name="Yankees", runs=5, hits=9, errors=0
            ),
            away=TeamGameLine(
                team_id=111, team_abbr="BOS", team_name="Red Sox", runs=3, hits=7, errors=1
            ),
        )
        edition = _make_edition(games=[game])
        data = edition.model_dump(mode="json")
        restored = Edition.model_validate(data)
        assert len(restored.games) == 1
        assert restored.games[0].game_id == 748293
        assert restored.games[0].home.runs == 5

    def test_round_trip_preserves_status(self):
        edition = _make_edition()
        data = edition.model_dump(mode="json")
        restored = Edition.model_validate(data)
        assert restored.edition.status == "published"


# ---------------------------------------------------------------------------
# 13. GenerationRun.record_phase transitions
# ---------------------------------------------------------------------------


class TestGenerationRunRecordPhase:
    def test_adds_new_phase(self):
        run = GenerationRun.start()
        run.record_phase("collecting", PhaseStatus.in_progress)
        assert len(run.phases) == 1
        assert run.phases[0].name == "collecting"
        assert run.phases[0].status == PhaseStatus.in_progress
        assert run.phases[0].started_at is not None

    def test_updates_existing_phase(self):
        run = GenerationRun.start()
        run.record_phase("collecting", PhaseStatus.in_progress)
        run.record_phase("collecting", PhaseStatus.completed, note="Done")
        assert len(run.phases) == 1
        assert run.phases[0].status == PhaseStatus.completed
        assert run.phases[0].completed_at is not None
        assert run.phases[0].note == "Done"

    def test_multiple_phases(self):
        run = GenerationRun.start()
        run.record_phase("collecting", PhaseStatus.completed)
        run.record_phase("normalizing", PhaseStatus.in_progress)
        run.record_phase("generating", PhaseStatus.pending)
        assert len(run.phases) == 3

    def test_failed_phase_sets_completed_at(self):
        run = GenerationRun.start()
        run.record_phase("collecting", PhaseStatus.in_progress)
        run.record_phase("collecting", PhaseStatus.failed, note="Provider timeout")
        assert run.phases[0].completed_at is not None
        assert run.phases[0].note == "Provider timeout"

    def test_skipped_phase(self):
        run = GenerationRun.start()
        run.record_phase("rendering", PhaseStatus.skipped, note="No changes")
        assert run.phases[0].status == PhaseStatus.skipped
        assert run.phases[0].completed_at is not None


# ---------------------------------------------------------------------------
# 14. GenerationRun.complete sets final_status and completed_at
# ---------------------------------------------------------------------------


class TestGenerationRunComplete:
    def test_complete_published(self):
        run = GenerationRun.start()
        assert run.completed_at is None
        run.complete(RunStatus.published)
        assert run.final_status == RunStatus.published
        assert run.completed_at is not None
        assert run.error is None

    def test_complete_failed_with_error(self):
        run = GenerationRun.start()
        run.complete(RunStatus.failed, error="MLB API unreachable")
        assert run.final_status == RunStatus.failed
        assert run.error == "MLB API unreachable"

    def test_complete_degraded(self):
        run = GenerationRun.start()
        run.complete(RunStatus.published_degraded)
        assert run.final_status == RunStatus.published_degraded

    def test_start_factory(self):
        run = GenerationRun.start()
        assert run.run_id is not None
        assert run.final_status == RunStatus.started
        assert isinstance(run.started_at, datetime)


# ---------------------------------------------------------------------------
# 15. EditionMetadata id format
# ---------------------------------------------------------------------------


class TestEditionMetadataId:
    def test_valid_id(self):
        meta = _make_edition_metadata(id="2026-07-13-0600")
        assert meta.id == "2026-07-13-0600"

    def test_valid_id_late_night(self):
        meta = _make_edition_metadata(id="2026-10-01-2330")
        assert meta.id == "2026-10-01-2330"

    def test_type_enum_values(self):
        for t in ("morning", "midday", "evening", "late", "final", "special"):
            meta = _make_edition_metadata(type=t)
            assert meta.type == t

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            _make_edition_metadata(type="afternoon")

    def test_invalid_status_raises(self):
        with pytest.raises(ValidationError):
            _make_edition_metadata(status="archived")

    def test_valid_statuses(self):
        for s in ("draft", "generating", "validating", "published", "failed", "published_degraded"):
            meta = _make_edition_metadata(status=s)
            assert meta.status == s

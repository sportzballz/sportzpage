# tests/unit/test_statistics.py
from __future__ import annotations
import pytest
from src.models.game import Game, GameStatus, TeamGameLine, LinescoreInning
from src.statistics.processor import StatisticsProcessor, NotablePerformance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _team(
    team_id: int = 1, abbr: str = "NYY", name: str = "Yankees", runs: int | None = None
) -> TeamGameLine:
    return TeamGameLine(team_id=team_id, team_abbr=abbr, team_name=name, runs=runs)


def _innings(*run_pairs: tuple[int, int]) -> list[LinescoreInning]:
    """Build a linescore from (away_runs, home_runs) pairs per inning."""
    return [
        LinescoreInning(inning=i + 1, away_runs=a, home_runs=h)
        for i, (a, h) in enumerate(run_pairs)
    ]


def _final_game(
    game_id: int,
    home_runs: int,
    away_runs: int,
    linescore: list[LinescoreInning] | None = None,
    tags: list[str] | None = None,
) -> Game:
    if linescore is None:
        # Build a basic 9-inning linescore placing all runs in the last inning
        innings = [(0, 0)] * 8 + [(away_runs, home_runs)]
        linescore = _innings(*innings)
    return Game(
        game_id=game_id,
        game_date="2026-07-04",
        status=GameStatus.final,
        home=_team(1, "NYY", "Yankees", home_runs),
        away=_team(2, "BOS", "Red Sox", away_runs),
        linescore=linescore,
        tags=tags or [],
    )


def _scheduled_game(game_id: int) -> Game:
    return Game(
        game_id=game_id,
        game_date="2026-07-04",
        status=GameStatus.scheduled,
        home=_team(1, "NYY", "Yankees"),
        away=_team(2, "BOS", "Red Sox"),
        linescore=[],
    )


# ---------------------------------------------------------------------------
# Tests: detect_notable_performances
# ---------------------------------------------------------------------------


class TestDetectNotablePerformances:
    proc = StatisticsProcessor()

    def test_walk_off_detection(self) -> None:
        # Home team wins 4-3, scores in bottom of 9th
        linescore = _innings(
            (1, 0),
            (0, 1),
            (1, 0),
            (0, 1),
            (1, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 3),
        )
        game = _final_game(1, home_runs=5, away_runs=3, linescore=linescore)
        result = self.proc.detect_notable_performances([game])
        assert 1 in result
        assert "walk-off" in result[1].tags
        assert result[1].performance_score > 0

    def test_no_walk_off_when_away_wins(self) -> None:
        # Away wins — home scores in last inning but loses
        linescore = _innings(
            (3, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 1),
        )
        game = _final_game(2, home_runs=1, away_runs=3, linescore=linescore)
        result = self.proc.detect_notable_performances([game])
        assert "walk-off" not in result[2].tags

    def test_extra_inning_detection(self) -> None:
        # 12-inning game
        linescore = _innings(*[(0, 0)] * 11 + [(0, 1)])
        game = _final_game(3, home_runs=1, away_runs=0, linescore=linescore)
        result = self.proc.detect_notable_performances([game])
        assert "extra-inning" in result[3].tags

    def test_shutout_detection(self) -> None:
        game = _final_game(4, home_runs=5, away_runs=0)
        result = self.proc.detect_notable_performances([game])
        assert "shutout" in result[4].tags

    def test_no_shutout_when_both_score(self) -> None:
        game = _final_game(5, home_runs=3, away_runs=1)
        result = self.proc.detect_notable_performances([game])
        assert "shutout" not in result[5].tags

    def test_scheduled_game_excluded(self) -> None:
        game = _scheduled_game(6)
        result = self.proc.detect_notable_performances([game])
        assert 6 not in result

    def test_existing_tags_preserved(self) -> None:
        game = _final_game(7, home_runs=3, away_runs=0, tags=["no-hitter"])
        result = self.proc.detect_notable_performances([game])
        assert "no-hitter" in result[7].tags
        assert "shutout" in result[7].tags

    def test_score_capped_at_one(self) -> None:
        # Walk-off + extra innings + shutout could exceed 1.0 raw
        linescore = _innings(*[(0, 0)] * 11 + [(0, 5)])
        game = _final_game(8, home_runs=5, away_runs=0, linescore=linescore)
        result = self.proc.detect_notable_performances([game])
        assert result[8].performance_score <= 1.0


# ---------------------------------------------------------------------------
# Tests: sort_games_by_editorial_significance
# ---------------------------------------------------------------------------


class TestSortGames:
    proc = StatisticsProcessor()

    def test_sorted_highest_first(self) -> None:
        games = [
            _final_game(10, 3, 2),
            _final_game(11, 5, 0),
            _final_game(12, 4, 3),
        ]
        performances = self.proc.detect_notable_performances(games)
        sorted_games = self.proc.sort_games_by_editorial_significance(games, performances)
        scores = [
            performances[g.game_id].performance_score
            for g in sorted_games
            if g.game_id in performances
        ]
        assert scores == sorted(scores, reverse=True)

    def test_scheduled_games_go_last(self) -> None:
        games = [
            _scheduled_game(20),
            _final_game(21, 3, 2),
        ]
        performances = self.proc.detect_notable_performances(games)
        sorted_games = self.proc.sort_games_by_editorial_significance(games, performances)
        assert sorted_games[0].game_id == 21
        assert sorted_games[1].game_id == 20


# ---------------------------------------------------------------------------
# Tests: qualification thresholds
# ---------------------------------------------------------------------------


class TestQualification:
    proc = StatisticsProcessor()

    def test_batter_qualified(self) -> None:
        assert self.proc.is_batter_qualified(400, 120) is True

    def test_batter_not_qualified(self) -> None:
        assert self.proc.is_batter_qualified(100, 120) is False

    def test_batter_zero_games_not_qualified(self) -> None:
        assert self.proc.is_batter_qualified(500, 0) is False

    def test_pitcher_qualified(self) -> None:
        assert self.proc.is_pitcher_qualified(130.0, 130) is True

    def test_pitcher_not_qualified(self) -> None:
        assert self.proc.is_pitcher_qualified(50.0, 130) is False

    def test_pitcher_zero_games_not_qualified(self) -> None:
        assert self.proc.is_pitcher_qualified(200.0, 0) is False


# ---------------------------------------------------------------------------
# Tests: detect_comeback
# ---------------------------------------------------------------------------


class TestDetectComeback:
    proc = StatisticsProcessor()

    def test_comeback_from_five_down(self) -> None:
        # Away leads 5-0 through 5 innings; home wins 6-5
        linescore = _innings(
            (2, 0),
            (1, 0),
            (1, 0),
            (1, 0),
            (0, 0),
            (0, 3),
            (0, 0),
            (0, 3),
            (0, 0),
        )
        game = _final_game(30, home_runs=6, away_runs=5, linescore=linescore)
        comeback = self.proc.detect_comeback(game)
        assert comeback == 5

    def test_no_comeback_wire_to_wire(self) -> None:
        # Home leads every inning
        linescore = _innings(
            (0, 3),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
            (0, 0),
        )
        game = _final_game(31, home_runs=3, away_runs=0, linescore=linescore)
        assert self.proc.detect_comeback(game) == 0

    def test_comeback_returns_zero_for_scheduled_game(self) -> None:
        game = _scheduled_game(32)
        assert self.proc.detect_comeback(game) == 0

    def test_comeback_empty_linescore(self) -> None:
        game = _final_game(33, home_runs=3, away_runs=2, linescore=[])
        assert self.proc.detect_comeback(game) == 0


# ---------------------------------------------------------------------------
# Tests: apply_notable_tags_to_games
# ---------------------------------------------------------------------------


class TestApplyNotableTags:
    proc = StatisticsProcessor()

    def test_tags_applied_to_game(self) -> None:
        game = _final_game(40, home_runs=5, away_runs=0)
        performances = {40: NotablePerformance(40, ["shutout", "extra-inning"], 0.9)}
        result = self.proc.apply_notable_tags_to_games([game], performances)
        assert "shutout" in result[0].tags
        assert "extra-inning" in result[0].tags

    def test_existing_tags_not_duplicated(self) -> None:
        game = _final_game(41, home_runs=5, away_runs=0, tags=["shutout"])
        performances = {41: NotablePerformance(41, ["shutout"], 0.5)}
        result = self.proc.apply_notable_tags_to_games([game], performances)
        assert result[0].tags.count("shutout") == 1

    def test_game_without_performance_unchanged(self) -> None:
        game = _final_game(42, home_runs=3, away_runs=2)
        result = self.proc.apply_notable_tags_to_games([game], {})
        assert result[0].tags == []

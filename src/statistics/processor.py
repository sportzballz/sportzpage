# src/statistics/processor.py
from __future__ import annotations
import logging
from src.models.game import Game, GameStatus
from src.models.standings import StandingsRow, DivisionStandings, WildCardStandings, Standings
from src.normalization.normalizer import NormalizedData

logger = logging.getLogger(__name__)


class NotablePerformance:
    """Detected notable performance signals for editorial scoring."""

    def __init__(self, game_id: int, tags: list[str], performance_score: float) -> None:
        self.game_id = game_id
        self.tags = tags
        self.performance_score = performance_score

    def __repr__(self) -> str:
        return f"NotablePerformance(game_id={self.game_id}, tags={self.tags}, score={self.performance_score:.2f})"


class StatisticsProcessor:
    """Computes derived statistics and detects notable performances."""

    # MLB batting qualification: 3.1 PA per team game played
    BATTING_PA_PER_GAME = 3.1
    # MLB pitching qualification: 1.0 IP per team game played
    PITCHING_IP_PER_GAME = 1.0

    def detect_notable_performances(self, games: list[Game]) -> dict[int, NotablePerformance]:
        """Detect walk-offs, extra innings, no-hitters, and score differential signals."""
        result: dict[int, NotablePerformance] = {}
        for game in games:
            if game.status != GameStatus.final:
                continue
            tags: list[str] = list(game.tags)  # preserve existing tags
            score = 0.0

            home_runs = game.home.runs or 0
            away_runs = game.away.runs or 0
            total_innings = len(game.linescore)

            # Extra innings
            if total_innings > 9:
                if "extra-inning" not in tags:
                    tags.append("extra-inning")
                score += 0.5

            # Walk-off: home team wins and scored in last inning
            if total_innings >= 9:
                last = game.linescore[-1]
                home_is_winner = home_runs > away_runs
                if (
                    home_is_winner
                    and last.home_runs
                    and last.home_runs > 0
                    and "walk-off" not in tags
                ):
                    tags.append("walk-off")
                    score += 0.8

            # Shut-out detection
            loser_runs = min(home_runs, away_runs)
            if loser_runs == 0 and max(home_runs, away_runs) > 0 and "shutout" not in tags:
                tags.append("shutout")
                score += 0.3

            # Drama score from margin
            diff = abs(home_runs - away_runs)
            if diff == 0:
                score += 0.3
            elif diff <= 1:
                score += 0.2

            # High-scoring game bonus
            total_runs = home_runs + away_runs
            score += min(total_runs / 20.0, 0.5)

            result[game.game_id] = NotablePerformance(game.game_id, tags, min(score, 1.0))
        return result

    def sort_games_by_editorial_significance(
        self,
        games: list[Game],
        performances: dict[int, NotablePerformance],
    ) -> list[Game]:
        """Sort final games by editorial significance (highest score first)."""

        def key(g: Game) -> float:
            if g.status != GameStatus.final:
                return -1.0
            perf = performances.get(g.game_id)
            return perf.performance_score if perf else 0.0

        return sorted(games, key=key, reverse=True)

    def is_batter_qualified(self, plate_appearances: int, team_games_played: int) -> bool:
        """Return True if a batter meets qualification threshold."""
        if team_games_played <= 0:
            return False
        return plate_appearances >= (self.BATTING_PA_PER_GAME * team_games_played)

    def is_pitcher_qualified(self, innings_pitched: float, team_games_played: int) -> bool:
        """Return True if a pitcher meets qualification threshold."""
        if team_games_played <= 0:
            return False
        return innings_pitched >= (self.PITCHING_IP_PER_GAME * team_games_played)

    def apply_notable_tags_to_games(
        self,
        games: list[Game],
        performances: dict[int, NotablePerformance],
    ) -> list[Game]:
        """Apply detected tags back to game objects in-place."""
        for game in games:
            if game.game_id in performances:
                perf = performances[game.game_id]
                game.tags = list(set(game.tags + perf.tags))
        return games

    def detect_comeback(self, game: Game) -> int:
        """Return the largest deficit overcome by the winning team. 0 if no comeback."""
        if game.status != GameStatus.final or not game.linescore:
            return 0
        home_runs = game.home.runs or 0
        away_runs = game.away.runs or 0
        home_won = home_runs > away_runs

        max_deficit = 0
        home_running = 0
        away_running = 0
        for inning in game.linescore:
            home_running += inning.home_runs or 0
            away_running += inning.away_runs or 0
            if home_won:
                deficit = away_running - home_running
            else:
                deficit = home_running - away_running
            if deficit > max_deficit:
                max_deficit = deficit
        return max_deficit

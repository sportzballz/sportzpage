# src/editorial/fallback.py
from __future__ import annotations

from src.models.game import Game, TeamBoxLine
from src.models.story import GameRecap, StoryType

AROUND_THE_LEAGUE_TEMPLATE = """\
{{ item_type }}: {{ description }}"""


def _ordinal(number: int) -> str:
    if 10 <= number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(number % 10, "th")
    return f"{number}{suffix}"


def _scoring_summary(game: Game, winner_is_home: bool) -> str | None:
    if not game.linescore:
        return None
    winner_runs = [
        (inning.home_runs or 0) if winner_is_home else (inning.away_runs or 0)
        for inning in game.linescore
    ]
    biggest = max(winner_runs, default=0)
    if biggest == 0:
        return None
    inning_number = game.linescore[winner_runs.index(biggest)].inning
    winner = game.home if winner_is_home else game.away
    return (
        f"Their biggest offensive inning came in the {_ordinal(inning_number)}, when "
        f"the {winner.team_name} scored {biggest} run{'s' if biggest != 1 else ''}."
    )


def _top_batter(lines: list[TeamBoxLine]) -> TeamBoxLine | None:
    eligible = [line for line in lines if (line.h or 0) > 0 or (line.rbi or 0) > 0]
    return max(eligible, key=lambda line: (line.rbi or 0, line.h or 0), default=None)


def _team_hits(game: Game, abbreviation: str) -> int:
    line = game.home if abbreviation == game.home.team_abbr else game.away
    return line.hits or 0


def _offense_summary(game: Game, winner_abbr: str, loser_abbr: str) -> str:
    sentence = (
        f"{winner_abbr} finished with {_team_hits(game, winner_abbr)} hits, while "
        f"{loser_abbr} collected {_team_hits(game, loser_abbr)}."
    )
    leaders: list[str] = []
    for abbreviation in (winner_abbr, loser_abbr):
        leader = _top_batter(game.batting_lines.get(abbreviation, []))
        if leader:
            hits = leader.h or 0
            detail = f"{hits} hit{'s' if hits != 1 else ''}"
            if leader.rbi:
                detail += f" and {leader.rbi} RBI"
            leaders.append(f"{leader.player_name} led {abbreviation} with {detail}")
    if leaders:
        sentence += " " + "; ".join(leaders) + "."
    return sentence


def generate_fallback_recap(game: Game) -> GameRecap:
    """Generate a deterministic recap from game data without AI."""
    home_runs = game.home.runs or 0
    away_runs = game.away.runs or 0
    winner = game.home if home_runs > away_runs else game.away
    loser = game.away if home_runs > away_runs else game.home

    headline = f"{winner.team_name} {winner.runs}, {loser.team_name} {loser.runs}"
    winner_is_home = winner is game.home
    opening = f"The {winner.team_name} defeated the {loser.team_name} {winner.runs}–{loser.runs}"
    if "walk-off" in game.tags:
        opening += " in walk-off fashion"
    if "extra-inning" in game.tags:
        opening += " in extra innings"
    if game.venue_name:
        opening += f" at {game.venue_name}"
    opening += "."
    scoring = _scoring_summary(game, winner_is_home)
    if scoring:
        opening += f" {scoring}"

    paragraphs = [opening, _offense_summary(game, winner.team_abbr, loser.team_abbr)]
    pitching: list[str] = []
    if game.winning_pitcher:
        pitching.append(f"{game.winning_pitcher.name} earned the win")
    if game.losing_pitcher:
        pitching.append(f"{game.losing_pitcher.name} took the loss")
    if game.save_pitcher:
        pitching.append(f"{game.save_pitcher.name} recorded the save")
    if pitching:
        paragraphs.append(". ".join(pitching) + ".")
    details: list[str] = []
    if game.time_of_game:
        details.append(f"The game lasted {game.time_of_game}")
    if game.attendance:
        details.append(f"the announced crowd was {game.attendance:,}")
    if details:
        paragraphs.append("; ".join(details) + ".")

    return GameRecap(
        headline=headline,
        deck=f"Final: {winner.team_abbr} {winner.runs}, {loser.team_abbr} {loser.runs}",
        byline="SportzBallz Staff",
        paragraphs=paragraphs,
        source_data_references=[f"game:{game.game_id}"],
        story_type=StoryType.game_recap,
        teams=[game.home.team_abbr, game.away.team_abbr],
        players=[],
        facts_used=[
            f"home_runs:{game.home.runs}",
            f"away_runs:{game.away.runs}",
            f"game_id:{game.game_id}",
        ],
        ai_generated=False,
        game_id=game.game_id,
        final_score=f"{winner.team_abbr} {winner.runs}, {loser.team_abbr} {loser.runs}",
        winning_pitcher=game.winning_pitcher,
        losing_pitcher=game.losing_pitcher,
        save_pitcher=game.save_pitcher,
        tags=list(game.tags),
    )

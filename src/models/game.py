# src/models/game.py
from __future__ import annotations
from datetime import datetime
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class GameStatus(str, Enum):
    final = "final"
    in_progress = "in_progress"
    scheduled = "scheduled"
    postponed = "postponed"
    delayed = "delayed"
    suspended = "suspended"


class LinescoreInning(BaseModel):
    inning: int = Field(description="Inning number (1-indexed).")
    away_runs: Optional[int] = Field(
        default=None, description="Runs scored by away team this inning."
    )
    home_runs: Optional[int] = Field(
        default=None, description="Runs scored by home team this inning."
    )


class TeamGameLine(BaseModel):
    team_id: int = Field(description="MLB team ID.")
    team_abbr: str = Field(description="Team abbreviation, e.g. NYY.")
    team_name: str = Field(description="Full team name.")
    runs: Optional[int] = Field(default=None, description="Runs scored. None if game not started.")
    hits: Optional[int] = Field(default=None)
    errors: Optional[int] = Field(default=None)


class Pitcher(BaseModel):
    player_id: int = Field(description="MLB player ID.")
    name: str = Field(description="Full player name.")
    handedness: Optional[str] = Field(default=None, description="L or R.")
    status: str = Field(
        default="probable",
        description="probable or confirmed.",
        examples=["probable", "confirmed"],
    )
    wins: Optional[int] = Field(
        default=None, description="Season wins at time of edition generation."
    )
    losses: Optional[int] = Field(default=None)
    era: Optional[float] = Field(default=None, description="Season ERA.")


class TeamBoxLine(BaseModel):
    """Per-player batting or pitching line for a box score."""

    player_name: str
    player_id: int = Field(default=0)
    position: Optional[str] = Field(default=None)
    ab: Optional[int] = Field(default=None, description="At-bats")
    r: Optional[int] = Field(default=None, description="Runs")
    h: Optional[int] = Field(default=None, description="Hits")
    rbi: Optional[int] = Field(default=None, description="RBI")
    bb: Optional[int] = Field(default=None, description="Walks")
    k: Optional[int] = Field(default=None, description="Strikeouts")
    avg: Optional[str] = Field(default=None, description="Season average, e.g. .285")
    # Pitching
    ip: Optional[str] = Field(default=None, description="Innings pitched, e.g. 6.1")
    er: Optional[int] = Field(default=None, description="Earned runs")
    hits_allowed: Optional[int] = Field(default=None)
    bb_allowed: Optional[int] = Field(default=None)
    k_pitched: Optional[int] = Field(default=None)
    era: Optional[str] = Field(default=None, description="Season ERA")
    decision: Optional[str] = Field(default=None, description="W, L, S, or H")
    pitches: Optional[int] = Field(default=None, description="Total pitches thrown")


class Game(BaseModel):
    """A single MLB game with all state needed to render scoreboard, schedule, and recap sections."""

    game_id: int = Field(description="MLB game PK.")
    game_date: str = Field(description="Game date in YYYY-MM-DD.")
    game_time_et: Optional[str] = Field(
        default=None, description="Scheduled start time in ET, e.g. 7:05 PM."
    )
    status: GameStatus = Field(description="Current game state.")
    inning: Optional[int] = Field(default=None, description="Current inning if in progress.")
    inning_state: Optional[str] = Field(default=None, description="Top, Middle, Bottom, End.")
    home: TeamGameLine = Field(description="Home team line score.")
    away: TeamGameLine = Field(description="Away team line score.")
    linescore: List[LinescoreInning] = Field(default_factory=list)
    home_probable_pitcher: Optional[Pitcher] = Field(default=None)
    away_probable_pitcher: Optional[Pitcher] = Field(default=None)
    winning_pitcher: Optional[Pitcher] = Field(
        default=None, description="Set when status is final."
    )
    losing_pitcher: Optional[Pitcher] = Field(default=None)
    save_pitcher: Optional[Pitcher] = Field(default=None)
    venue_name: Optional[str] = Field(default=None)
    venue_city: Optional[str] = Field(default=None)
    tv_broadcasts: List[str] = Field(
        default_factory=list, description="TV/streaming network names."
    )
    weather_description: Optional[str] = Field(
        default=None, description="Short weather string for previews."
    )
    postponement_reason: Optional[str] = Field(
        default=None, description="Reason for postponement or delay."
    )
    attendance: Optional[int] = Field(
        default=None,
        description="Reported attendance. Never rendered for scheduled games — only final.",
    )
    time_of_game: Optional[str] = Field(default=None, description="Duration, e.g. 3:12.")
    is_doubleheader: bool = Field(default=False)
    doubleheader_game_num: Optional[int] = Field(default=None, description="1 or 2.")
    tags: List[str] = Field(
        default_factory=list,
        description="Notable tags: walk-off, extra-inning, no-hitter, perfect-game, shutout, etc.",
    )
    series_description: Optional[str] = Field(default=None, description="e.g. ALDS Game 3.")
    recap_anchor: Optional[str] = Field(
        default=None, description="Anchor ID linking scoreboard entry to recap."
    )
    batting_lines: dict[str, list[TeamBoxLine]] = Field(
        default_factory=dict,
        description="Keyed by team_abbr. List of batter lines in batting order.",
    )
    pitching_lines: dict[str, list[TeamBoxLine]] = Field(
        default_factory=dict, description="Keyed by team_abbr. List of pitcher lines in order used."
    )
    boxscore_notes: List[str] = Field(
        default_factory=list,
        description="Game notes such as extra-base hits, runners left on base, and umpires.",
    )

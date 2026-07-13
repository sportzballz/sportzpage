# src/models/leaders.py
from __future__ import annotations
from pydantic import BaseModel, Field

BATTING_CATEGORIES = [
    "avg",
    "obp",
    "slg",
    "ops",
    "hr",
    "rbi",
    "r",
    "h",
    "doubles",
    "triples",
    "sb",
    "bb",
    "so",
    "tb",
    "xbh",
    "war",
]

PITCHING_CATEGORIES = [
    "era",
    "wins",
    "k",
    "whip",
    "saves",
    "holds",
    "ip",
    "qs",
    "cg",
    "sho",
    "opp_avg",
    "k9",
    "bb9",
    "hr9",
    "war",
]


class LeaderEntry(BaseModel):
    """A single player entry in a league-leaders leaderboard."""

    rank: int = Field(ge=1, description="Rank within this category (1 = best).")
    player_id: int = Field(description="MLB player ID.")
    player_name: str
    team_abbr: str
    position: str = Field(description="Primary position abbreviation, e.g. SP, CF, 1B.")
    value: str = Field(description="Formatted stat value, e.g. .342 or 2.81 or 23.")
    games_played: int
    league: str = Field(description="AL or NL.")
    qualified: bool = Field(description="Whether the player meets qualification thresholds.")


class LeagueLeaders(BaseModel):
    """All leader boards for a given edition."""

    batting: dict[str, list[LeaderEntry]] = Field(
        description="Keyed by batting category (avg, obp, slg, ops, hr, rbi, r, h, doubles, triples, sb, bb, so, tb, xbh, war).",
    )
    pitching: dict[str, list[LeaderEntry]] = Field(
        description="Keyed by pitching category (era, wins, k, whip, saves, holds, ip, qs, cg, sho, opp_avg, k9, bb9, hr9, war).",
    )


class TeamPerformer(BaseModel):
    """A single player's notable performance in a game."""

    player_name: str
    player_id: int = Field(default=0)
    team_abbr: str
    stat_line: str = Field(
        description="Human-readable stat line, e.g. '3-for-4, 2 HR, 5 RBI' or '7 IP, 1 ER, 9 K'"
    )
    role: str = Field(description="'batter' or 'pitcher'")
    game_id: int = Field(default=0)


class TeamGameLeaders(BaseModel):
    """Key performers for a single game."""

    game_id: int
    away_abbr: str
    home_abbr: str
    performers: list[TeamPerformer] = Field(default_factory=list)

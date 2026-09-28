from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.game import Game
from src.models.leaders import LeagueLeaders


class PostseasonSeries(BaseModel):
    key: str
    round_name: str
    league: str = "MLB"
    away_team: str
    home_team: str
    away_wins: int = 0
    home_wins: int = 0
    wins_required: int = 4
    status: str
    games: list[Game] = Field(default_factory=list)


class Postseason(BaseModel):
    games: list[Game] = Field(default_factory=list)
    series: list[PostseasonSeries] = Field(default_factory=list)
    league_leaders: LeagueLeaders | None = None

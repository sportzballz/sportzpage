# src/models/standings.py
from __future__ import annotations
from typing import List, Optional, Union
from pydantic import BaseModel, Field


class StandingsRow(BaseModel):
    """A single team row in a division standings table."""

    team_id: int = Field(description="MLB team ID.")
    team_abbr: str = Field(description="Team abbreviation, e.g. NYY.")
    team_name: str = Field(description="Full team name.")
    wins: int = Field(description="Season wins.")
    losses: int = Field(description="Season losses.")
    pct: float = Field(description="Winning percentage.")
    games_back: Union[float, str] = Field(
        description="Games behind division leader. 0.0 for the leader."
    )
    last_10: str = Field(description="Record over last 10 games, e.g. 6-4.")
    streak: str = Field(description="Current streak, e.g. W3 or L1.")
    home_record: str = Field(description="Home record, e.g. 30-20.")
    away_record: str = Field(description="Away record, e.g. 28-22.")
    run_differential: int = Field(description="Runs scored minus runs allowed.")
    wild_card_gb: Optional[Union[float, str]] = Field(default=None)
    eliminated: bool = Field(default=False)
    magic_number: Optional[int] = Field(default=None)


class DivisionStandings(BaseModel):
    division_id: int
    division_name: str = Field(description="e.g. AL East.")
    rows: List[StandingsRow] = Field(min_length=1)


class WildCardStandings(BaseModel):
    league: str = Field(description="AL or NL.")
    rows: List[StandingsRow] = Field(min_length=1)


class Standings(BaseModel):
    divisions: List[DivisionStandings] = Field(description="All 6 MLB divisions.")
    wild_cards: List[WildCardStandings] = Field(description="AL and NL wild card standings.")

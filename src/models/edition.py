# src/models/edition.py
from __future__ import annotations
from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from src.models.game import Game
from src.models.standings import Standings
from src.models.leaders import LeagueLeaders, TeamGameLeaders, TeamSeasonLeaders
from src.models.story import Story, GameRecap
from src.models.transactions import Transaction
from src.models.injuries import Injury
from src.models.history import HistoricalItem
from src.models.freshness import DataFreshness


EditionType = Literal["morning", "midday", "evening", "late", "final", "special"]
EditionStatus = Literal[
    "draft", "generating", "validating", "published", "failed", "published_degraded"
]


class EditionMetadata(BaseModel):
    """Top-level metadata identifying this edition."""

    id: str = Field(
        description="Edition ID in the form YYYY-MM-DD-HHMM, e.g. 2026-07-13-0600.",
        examples=["2026-07-13-0600"],
    )
    type: EditionType = Field(description="Edition type controlling content emphasis.")
    date: str = Field(description="Publication date in YYYY-MM-DD format.")
    generated_at: datetime = Field(description="ISO 8601 timestamp when generation completed.")
    data_current_through: datetime = Field(
        description="Latest data timestamp included in this edition."
    )
    timezone: str = Field(
        default="America/New_York", description="Display timezone for all times on the page."
    )
    status: EditionStatus = Field(description="Current lifecycle status of this edition.")


class GenerationMetadata(BaseModel):
    pipeline_version: str = Field(description="semver of the daily-sports-page package.")
    python_version: str = Field(default="")
    ai_provider: Optional[str] = Field(default=None)
    ai_model: Optional[str] = Field(default=None)
    ai_fallbacks: int = Field(default=0)
    total_duration_seconds: Optional[float] = Field(default=None)
    data_freshness: DataFreshness = Field(default_factory=DataFreshness)


class Edition(BaseModel):
    """Root Edition JSON document. All HTML rendering is a pure function of this model."""

    edition: EditionMetadata
    lead_story: Optional[Story] = Field(default=None)
    secondary_stories: List[Story] = Field(
        default_factory=list, description="3–6 secondary front-page stories."
    )
    games: List[Game] = Field(default_factory=list)
    standings: Optional[Standings] = Field(default=None)
    league_leaders: Optional[LeagueLeaders] = Field(default=None)
    game_recaps: List[GameRecap] = Field(default_factory=list)
    around_the_league: List[Story] = Field(default_factory=list)
    transactions: List[Transaction] = Field(default_factory=list)
    injuries: List[Injury] = Field(default_factory=list)
    historical_items: List[HistoricalItem] = Field(default_factory=list)
    team_game_leaders: List[TeamGameLeaders] = Field(default_factory=list)
    team_season_leaders: List[TeamSeasonLeaders] = Field(default_factory=list)
    generation_metadata: GenerationMetadata = Field(
        default_factory=lambda: GenerationMetadata(pipeline_version="0.1.0")
    )

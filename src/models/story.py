# src/models/story.py
from __future__ import annotations
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field
from src.models.game import Pitcher


class StoryType(str, Enum):
    lead = "lead"
    secondary = "secondary"
    game_recap = "game_recap"
    division_snapshot = "division_snapshot"
    wild_card_watch = "wild_card_watch"
    rookie_watch = "rookie_watch"
    editorial = "editorial"
    transaction_summary = "transaction_summary"


class Story(BaseModel):
    """An AI-generated or deterministic editorial story."""

    headline: str = Field(
        description="Story headline. Must not be invented — grounded in structured data."
    )
    deck: str = Field(description="Subheadline / summary sentence.")
    byline: str = Field(default="SportzBallz Staff")
    paragraphs: List[str] = Field(min_length=1, description="Body paragraphs.")
    source_data_references: List[str] = Field(
        default_factory=list,
        description="Keys from Edition JSON that ground this story, e.g. game:748293.",
    )
    story_type: StoryType
    teams: List[str] = Field(default_factory=list, description="Team abbreviations mentioned.")
    players: List[str] = Field(default_factory=list, description="Player names mentioned.")
    facts_used: List[str] = Field(
        default_factory=list,
        description="Enumeration of facts from structured data used in this story.",
    )
    ai_generated: bool = Field(default=True)
    source_name: Optional[str] = Field(default=None)
    source_url: Optional[str] = Field(default=None)


class GameRecap(Story):
    """A game recap story. Extends Story with game-specific fields."""

    game_id: int = Field(description="MLB game PK this recap covers.")
    final_score: str = Field(description="Formatted final score, e.g. NYY 5, BOS 3.")
    winning_pitcher: Optional[Pitcher] = Field(default=None)
    losing_pitcher: Optional[Pitcher] = Field(default=None)
    save_pitcher: Optional[Pitcher] = Field(default=None)
    tags: List[str] = Field(
        default_factory=list,
        description="walk-off, extra-inning, no-hitter, perfect-game, shutout, doubleheader, etc.",
    )

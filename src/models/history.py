# src/models/history.py
from __future__ import annotations
from pydantic import BaseModel, Field


class HistoricalItem(BaseModel):
    """A 'this day in baseball history' item."""

    year: int = Field(ge=1839)
    headline: str = Field(description="Brief summary of the historical event.")
    description: str = Field(description="One to two sentence description.")
    teams: list[str] = Field(default_factory=list)
    players: list[str] = Field(default_factory=list)
    source: str = Field(description="Data source attribution for this historical fact.")
    verified: bool = Field(default=True)

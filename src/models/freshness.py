# src/models/freshness.py
from __future__ import annotations
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class DataFreshness(BaseModel):
    """Per-section data freshness timestamps for display and staleness warnings."""

    live_scores_as_of: Optional[datetime] = Field(default=None)
    standings_as_of: Optional[datetime] = Field(default=None)
    schedule_as_of: Optional[datetime] = Field(default=None)
    league_leaders_as_of: Optional[datetime] = Field(default=None)
    transactions_as_of: Optional[datetime] = Field(default=None)
    injuries_as_of: Optional[datetime] = Field(default=None)
    historical_as_of: Optional[datetime] = Field(default=None)
    max_age_warnings: List[str] = Field(
        default_factory=list,
        description="Human-readable warnings for sections exceeding freshness thresholds.",
    )

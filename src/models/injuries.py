# src/models/injuries.py
from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class RosterStatus(str, Enum):
    ten_day_il = "10-day-il"
    fifteen_day_il = "15-day-il"
    sixty_day_il = "60-day-il"
    day_to_day = "day-to-day"
    out = "out"


class InjuryConfidence(str, Enum):
    confirmed = "confirmed"
    reported = "reported"
    speculative = "speculative"


class Injury(BaseModel):
    """An injury report entry. The system MUST NOT invent return dates."""

    player_id: int
    player_name: str
    team_abbr: str
    injury_description: str = Field(
        description="Nature of the injury, e.g. right hamstring strain."
    )
    roster_status: RosterStatus
    date_of_injury: Optional[date] = Field(default=None)
    expected_return: Optional[str] = Field(
        default=None,
        description=(
            "Expected return timeline as a string, e.g. 'mid-August' or 'day-to-day'. "
            "NEVER generated — only populated from verified provider data."
        ),
    )
    confidence_level: InjuryConfidence
    latest_update: Optional[str] = Field(default=None)
    update_timestamp: Optional[datetime] = Field(default=None)

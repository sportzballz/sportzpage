# src/models/transactions.py
from __future__ import annotations
from datetime import date, datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    trade = "trade"
    dfa = "dfa"
    released = "released"
    signed = "signed"
    optioned = "optioned"
    recalled = "recalled"
    injury = "injury"
    placed_on_il = "placed_on_il"
    activated = "activated"
    claimed = "claimed"
    retired = "retired"
    other = "other"


class Transaction(BaseModel):
    """A single roster transaction."""

    transaction_id: str = Field(description="Provider-assigned transaction ID for deduplication.")
    team_abbr: str
    team_name: str
    player_name: str
    player_id: Optional[int] = Field(default=None)
    transaction_type: TransactionType
    effective_date: date
    explanation: str = Field(description="Human-readable description of the transaction.")
    source_timestamp: datetime = Field(description="When the provider reported this transaction.")

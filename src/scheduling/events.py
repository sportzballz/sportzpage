# src/scheduling/events.py
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class EventTrigger(Enum):
    POST_GAME = "post_game"
    POST_TRANSACTION = "post_transaction"
    PRE_FIRST_GAME = "pre_first_game"
    MANUAL = "manual"


@dataclass
class TriggerEvent:
    trigger: EventTrigger
    edition_type: str
    context: dict = field(default_factory=dict)


def build_post_game_event(game_id: str, edition_type: str = "late") -> TriggerEvent:
    return TriggerEvent(
        trigger=EventTrigger.POST_GAME,
        edition_type=edition_type,
        context={"game_id": game_id},
    )


def build_post_transaction_event(transaction_id: str, edition_type: str = "midday") -> TriggerEvent:
    return TriggerEvent(
        trigger=EventTrigger.POST_TRANSACTION,
        edition_type=edition_type,
        context={"transaction_id": transaction_id},
    )


def build_manual_event(edition_type: str = "morning") -> TriggerEvent:
    return TriggerEvent(
        trigger=EventTrigger.MANUAL,
        edition_type=edition_type,
        context={},
    )

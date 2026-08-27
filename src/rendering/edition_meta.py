from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
VOLUME_EPOCH = date(2026, 4, 1)


def format_eastern_time(value: datetime | None) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=EASTERN)
    return value.astimezone(EASTERN).strftime("%-I:%M %p %Z")


def daypart_edition(value: datetime | None) -> str:
    if value is None:
        return "Edition"
    if value.tzinfo is None:
        value = value.replace(tzinfo=EASTERN)
    hour = value.astimezone(EASTERN).hour
    if hour < 12:
        return "Morning Edition"
    if hour < 17:
        return "Afternoon Edition"
    return "Evening Edition"


def volume_number(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=EASTERN)
        edition_date = value.astimezone(EASTERN).date()
    else:
        edition_date = value if isinstance(value, date) else date.fromisoformat(value)
    number = max(1, (edition_date - VOLUME_EPOCH).days)
    numerals = (
        (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"),
        (100, "C"), (90, "XC"), (50, "L"), (40, "XL"),
        (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
    )
    result = []
    for value, numeral in numerals:
        count, number = divmod(number, value)
        result.append(numeral * count)
    return "".join(result)

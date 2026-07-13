# src/scheduling/scheduler.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
import re

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore


@dataclass
class ScheduleEntry:
    time: str  # HH:MM derived from cron
    edition: str


@dataclass
class Schedule:
    timezone: str
    entries: list[ScheduleEntry] = field(default_factory=list)


def _cron_to_hhmm(cron: str) -> str:
    """Parse a simple daily cron expression '0 6 * * *' -> '06:00'."""
    parts = cron.strip().split()
    minute = int(parts[0])
    hour = int(parts[1])
    return f"{hour:02d}:{minute:02d}"


def load_schedule(path: "str | Path" = "config/schedules.yaml") -> Schedule:
    if yaml is None:
        raise ImportError("PyYAML is required to load schedules.")
    path = Path(path)
    with path.open() as f:
        data = yaml.safe_load(f)

    tz = data.get("timezone", "America/New_York")
    entries: list[ScheduleEntry] = []
    for item in data.get("editions", []):
        edition_type = item.get("type", "")
        cron = item.get("cron", "")
        hhmm = _cron_to_hhmm(cron)
        entries.append(ScheduleEntry(time=hhmm, edition=edition_type))

    # Sort by time
    entries.sort(key=lambda e: e.time)
    return Schedule(timezone=tz, entries=entries)


def _parse_time(hhmm: str) -> tuple[int, int]:
    h, m = hhmm.split(":")
    return int(h), int(m)


def _today_dt(hour: int, minute: int, now: datetime) -> datetime:
    """Return today's date at the given hour/minute in the same tzinfo as now."""
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def get_current_edition_type(schedule: Schedule, now: Optional[datetime] = None) -> str:
    if now is None:
        now = datetime.now(timezone.utc)

    best: Optional[ScheduleEntry] = None
    best_dt: Optional[datetime] = None

    for entry in schedule.entries:
        h, m = _parse_time(entry.time)
        candidate = _today_dt(h, m, now)
        if candidate <= now:
            if best_dt is None or candidate > best_dt:
                best = entry
                best_dt = candidate

    if best is None:
        # Before first entry of day — return first entry's edition or "morning"
        if schedule.entries:
            return schedule.entries[0].edition
        return "morning"

    return best.edition


def get_next_run(schedule: Schedule, now: Optional[datetime] = None) -> tuple[datetime, str]:
    if now is None:
        now = datetime.now(timezone.utc)

    for entry in schedule.entries:
        h, m = _parse_time(entry.time)
        candidate = _today_dt(h, m, now)
        if candidate > now:
            return candidate, entry.edition

    # All entries passed today — next is first entry tomorrow
    first = schedule.entries[0]
    h, m = _parse_time(first.time)
    tomorrow = now + timedelta(days=1)
    next_dt = tomorrow.replace(hour=h, minute=m, second=0, microsecond=0)
    return next_dt, first.edition


def is_overlapping_window(
    schedule: Schedule, run_duration_minutes: int = 30, now: Optional[datetime] = None
) -> bool:
    if now is None:
        now = datetime.now(timezone.utc)

    for entry in schedule.entries:
        h, m = _parse_time(entry.time)
        scheduled = _today_dt(h, m, now)
        if scheduled <= now <= scheduled + timedelta(minutes=run_duration_minutes):
            return True
    return False

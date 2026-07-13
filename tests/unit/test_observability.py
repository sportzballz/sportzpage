# tests/unit/test_observability.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.scheduling.scheduler import (
    Schedule,
    ScheduleEntry,
    load_schedule,
    get_current_edition_type,
    get_next_run,
    is_overlapping_window,
)
from src.scheduling.events import (
    EventTrigger,
    TriggerEvent,
    build_post_game_event,
    build_post_transaction_event,
    build_manual_event,
)
from src.observability.health import (
    SectionHealth,
    HealthReport,
    build_health_report,
    format_health_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SCHEDULE_PATH = Path("config/schedules.yaml")


def _make_schedule() -> Schedule:
    return Schedule(
        timezone="America/New_York",
        entries=[
            ScheduleEntry(time="01:30", edition="final"),
            ScheduleEntry(time="06:00", edition="morning"),
            ScheduleEntry(time="12:00", edition="midday"),
            ScheduleEntry(time="17:00", edition="evening"),
            ScheduleEntry(time="23:30", edition="late"),
        ],
    )


def _now_at(hour: int, minute: int) -> datetime:
    return datetime(2026, 7, 13, hour, minute, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 1. load_schedule — loads YAML, entries in order
# ---------------------------------------------------------------------------


def test_load_schedule_loads_yaml():
    schedule = load_schedule(SCHEDULE_PATH)
    assert schedule.timezone == "America/New_York"
    assert len(schedule.entries) >= 4


def test_load_schedule_entries_sorted():
    schedule = load_schedule(SCHEDULE_PATH)
    times = [e.time for e in schedule.entries]
    assert times == sorted(times)


def test_load_schedule_edition_types_present():
    schedule = load_schedule(SCHEDULE_PATH)
    edition_types = {e.edition for e in schedule.entries}
    assert "morning" in edition_types
    assert "late" in edition_types


# ---------------------------------------------------------------------------
# 2. get_current_edition_type — correct edition at various times
# ---------------------------------------------------------------------------


def test_get_current_edition_before_first():
    schedule = _make_schedule()
    # 00:30 is after final (01:30) hasn't run yet today — before first entry "final" at 01:30
    now = _now_at(0, 30)
    # 00:30 is before 01:30, so no entries have passed — should return first edition
    result = get_current_edition_type(schedule, now)
    assert result == "final"  # first entry alphabetically/by time


def test_get_current_edition_morning():
    schedule = _make_schedule()
    result = get_current_edition_type(schedule, _now_at(7, 0))
    assert result == "morning"


def test_get_current_edition_midday():
    schedule = _make_schedule()
    result = get_current_edition_type(schedule, _now_at(13, 0))
    assert result == "midday"


def test_get_current_edition_late():
    schedule = _make_schedule()
    result = get_current_edition_type(schedule, _now_at(23, 45))
    assert result == "late"


# ---------------------------------------------------------------------------
# 3. get_next_run — returns next future entry
# ---------------------------------------------------------------------------


def test_get_next_run_returns_future():
    schedule = _make_schedule()
    now = _now_at(7, 0)
    next_dt, edition = get_next_run(schedule, now)
    assert next_dt > now
    assert edition == "midday"


def test_get_next_run_wraps_to_tomorrow():
    schedule = _make_schedule()
    now = _now_at(23, 45)  # after all entries
    next_dt, edition = get_next_run(schedule, now)
    assert next_dt.date() > now.date()
    assert edition == "final"


# ---------------------------------------------------------------------------
# 4. build_health_report — stale / healthy detection
# ---------------------------------------------------------------------------


def _make_edition(
    standings_age_minutes: float | None = None, live_scores_age_minutes: float | None = None
):
    now = datetime.now(timezone.utc)

    freshness = SimpleNamespace(
        live_scores_as_of=(now - timedelta(minutes=live_scores_age_minutes))
        if live_scores_age_minutes is not None
        else None,
        standings_as_of=(now - timedelta(minutes=standings_age_minutes))
        if standings_age_minutes is not None
        else None,
        schedule_as_of=None,
        league_leaders_as_of=None,
        transactions_as_of=None,
        injuries_as_of=None,
        historical_as_of=None,
    )
    gen_meta = SimpleNamespace(data_freshness=freshness)
    edition_meta = SimpleNamespace(id="2026-07-13-0600")
    return SimpleNamespace(edition=edition_meta, generation_metadata=gen_meta)


def test_build_health_report_stale_section():
    edition = _make_edition(standings_age_minutes=120)  # exceeds default 60 min max
    report = build_health_report(edition, settings=None)
    standings = next(s for s in report.sections if s.section == "standings")
    assert standings.is_stale is True


def test_build_health_report_healthy_section():
    edition = _make_edition(standings_age_minutes=10)  # well within 60 min max
    report = build_health_report(edition, settings=None)
    standings = next(s for s in report.sections if s.section == "standings")
    assert standings.is_stale is False


def test_build_health_report_overall_healthy_false_when_stale():
    edition = _make_edition(standings_age_minutes=200)
    report = build_health_report(edition, settings=None)
    assert report.overall_healthy is False


def test_build_health_report_edition_id():
    edition = _make_edition()
    report = build_health_report(edition, settings=None)
    assert report.edition_id == "2026-07-13-0600"


# ---------------------------------------------------------------------------
# 5. format_health_report — non-empty string with edition_id
# ---------------------------------------------------------------------------


def test_format_health_report_non_empty():
    edition = _make_edition(standings_age_minutes=10)
    report = build_health_report(edition, settings=None)
    result = format_health_report(report)
    assert isinstance(result, str)
    assert len(result) > 0


def test_format_health_report_contains_edition_id():
    edition = _make_edition()
    report = build_health_report(edition, settings=None)
    result = format_health_report(report)
    assert "2026-07-13-0600" in result


# ---------------------------------------------------------------------------
# 6. SectionHealth.is_stale logic
# ---------------------------------------------------------------------------


def test_section_health_stale_when_age_exceeds_max():
    sh = SectionHealth(
        section="standings",
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=90),
        max_age_minutes=60,
        is_stale=True,
        age_minutes=90.0,
    )
    assert sh.is_stale is True


def test_section_health_not_stale_when_within_max():
    sh = SectionHealth(
        section="standings",
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        max_age_minutes=60,
        is_stale=False,
        age_minutes=30.0,
    )
    assert sh.is_stale is False


# ---------------------------------------------------------------------------
# 7. TriggerEvent construction
# ---------------------------------------------------------------------------


def test_build_post_game_event():
    event = build_post_game_event("gid-123")
    assert event.trigger == EventTrigger.POST_GAME
    assert event.edition_type == "late"
    assert event.context["game_id"] == "gid-123"


def test_build_post_game_event_custom_edition():
    event = build_post_game_event("gid-456", edition_type="final")
    assert event.edition_type == "final"


def test_build_manual_event():
    event = build_manual_event()
    assert event.trigger == EventTrigger.MANUAL
    assert event.edition_type == "morning"


def test_build_manual_event_custom_edition():
    event = build_manual_event(edition_type="evening")
    assert event.edition_type == "evening"


def test_build_post_transaction_event():
    event = build_post_transaction_event("txn-789")
    assert event.trigger == EventTrigger.POST_TRANSACTION
    assert event.edition_type == "midday"
    assert event.context["transaction_id"] == "txn-789"

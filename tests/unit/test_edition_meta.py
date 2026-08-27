from datetime import date, datetime, timezone

from src.rendering.edition_meta import daypart_edition, format_eastern_time, volume_number


def test_formats_utc_timestamp_in_eastern_time() -> None:
    assert format_eastern_time(datetime(2026, 8, 27, 16, 7, tzinfo=timezone.utc)) == "12:07 PM EDT"


def test_volume_is_elapsed_days_since_april_first_2026() -> None:
    assert volume_number(date(2026, 8, 27)) == "CXLVIII"
    assert volume_number(datetime(2026, 8, 28, 1, 0, tzinfo=timezone.utc)) == "CXLVIII"


def test_daypart_edition_uses_eastern_boundaries() -> None:
    assert daypart_edition(datetime(2026, 8, 27, 15, 59, tzinfo=timezone.utc)) == "Morning Edition"
    assert daypart_edition(datetime(2026, 8, 27, 16, 0, tzinfo=timezone.utc)) == "Afternoon Edition"
    assert daypart_edition(datetime(2026, 8, 27, 20, 59, tzinfo=timezone.utc)) == "Afternoon Edition"
    assert daypart_edition(datetime(2026, 8, 27, 21, 0, tzinfo=timezone.utc)) == "Evening Edition"

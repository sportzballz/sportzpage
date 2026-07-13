# src/observability/health.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


@dataclass
class SectionHealth:
    section: str
    updated_at: Optional[datetime]
    max_age_minutes: int
    is_stale: bool
    age_minutes: Optional[float]


@dataclass
class HealthReport:
    edition_id: str
    generated_at: datetime
    sections: list[SectionHealth] = field(default_factory=list)
    overall_healthy: bool = True


# Mapping from DataFreshness field names to section display names
_FRESHNESS_FIELDS = {
    "live_scores_as_of": ("live_scores", 15),
    "standings_as_of": ("standings", 60),
    "schedule_as_of": ("schedule", 120),
    "league_leaders_as_of": ("league_leaders", 60),
    "transactions_as_of": ("transactions", 120),
    "injuries_as_of": ("injuries", 120),
    "historical_as_of": ("historical", 1440),
}


def build_health_report(edition: Any, settings: Any) -> HealthReport:
    now = datetime.now(timezone.utc)
    edition_id = getattr(getattr(edition, "edition", None), "id", "unknown")
    sections: list[SectionHealth] = []

    freshness = getattr(getattr(edition, "generation_metadata", None), "data_freshness", None)

    # Try to get per-section max age from settings; fall back to defaults
    def _max_age(section_name: str, default: int) -> int:
        if settings is None:
            return default
        # Check settings.freshness_limits dict or attribute pattern
        fl = getattr(settings, "freshness_limits", None)
        if isinstance(fl, dict):
            return fl.get(section_name, default)
        return default

    for field_name, (section_name, default_max) in _FRESHNESS_FIELDS.items():
        updated_at: Optional[datetime] = None
        if freshness is not None:
            updated_at = getattr(freshness, field_name, None)

        max_age = _max_age(section_name, default_max)

        age_minutes: Optional[float] = None
        is_stale = False

        if updated_at is not None:
            # Ensure timezone-aware comparison
            ts = updated_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_minutes = (now - ts).total_seconds() / 60.0
            is_stale = age_minutes > max_age
        else:
            # No timestamp — treat as stale
            is_stale = True

        sections.append(
            SectionHealth(
                section=section_name,
                updated_at=updated_at,
                max_age_minutes=max_age,
                is_stale=is_stale,
                age_minutes=age_minutes,
            )
        )

    overall_healthy = not any(s.is_stale for s in sections)
    return HealthReport(
        edition_id=edition_id,
        generated_at=now,
        sections=sections,
        overall_healthy=overall_healthy,
    )


def format_health_report(report: HealthReport) -> str:
    lines = [
        f"Health Report — Edition: {report.edition_id}",
        f"Generated at: {report.generated_at.isoformat()}",
        f"Overall healthy: {report.overall_healthy}",
        "",
    ]
    for s in report.sections:
        age_str = f"{s.age_minutes:.1f} min" if s.age_minutes is not None else "unknown"
        stale_str = "STALE" if s.is_stale else "OK"
        lines.append(f"  [{stale_str}] {s.section}: age={age_str}, max={s.max_age_minutes} min")
    return "\n".join(lines)

# src/models/run.py
from __future__ import annotations
from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4
from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    started = "started"
    collecting = "collecting"
    normalizing = "normalizing"
    generating = "generating"
    validating = "validating"
    rendering = "rendering"
    publishing = "publishing"
    published = "published"
    failed = "failed"
    published_degraded = "published_degraded"


class PhaseStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class RunPhase(BaseModel):
    name: str = Field(description="Phase name matching RunStatus values.")
    status: PhaseStatus
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    note: Optional[str] = Field(default=None)

    @property
    def duration_seconds(self) -> Optional[float]:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class ProviderStatus(BaseModel):
    provider: str
    available: bool
    response_time_ms: Optional[float] = Field(default=None)
    error: Optional[str] = Field(default=None)
    used_cache: bool = False


class GenerationRun(BaseModel):
    """Observability record for a single pipeline execution."""

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    edition_id: Optional[str] = Field(default=None)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = Field(default=None)
    phases: List[RunPhase] = Field(default_factory=list)
    provider_statuses: List[ProviderStatus] = Field(default_factory=list)
    final_status: RunStatus = Field(default=RunStatus.started)
    error: Optional[str] = Field(default=None)
    ai_used: bool = False
    ai_fallback_count: int = Field(default=0)
    game_count: int = Field(default=0)
    story_count: int = Field(default=0)
    leader_category_count: int = Field(default=0)
    published_url: Optional[str] = Field(default=None)

    @classmethod
    def start(cls) -> "GenerationRun":
        return cls()

    def record_phase(self, name: str, status: PhaseStatus, note: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc)
        for phase in self.phases:
            if phase.name == name:
                phase.status = status
                if status == PhaseStatus.in_progress:
                    phase.started_at = now
                elif status in (PhaseStatus.completed, PhaseStatus.failed, PhaseStatus.skipped):
                    phase.completed_at = now
                if note:
                    phase.note = note
                return
        self.phases.append(
            RunPhase(
                name=name,
                status=status,
                started_at=now if status == PhaseStatus.in_progress else None,
                completed_at=now if status != PhaseStatus.in_progress else None,
                note=note,
            )
        )

    def complete(self, status: RunStatus, error: Optional[str] = None) -> None:
        self.final_status = status
        self.completed_at = datetime.now(timezone.utc)
        if error:
            self.error = error

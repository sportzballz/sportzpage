from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.generate_market_editions as market_script
from src.markets import MARKETS_BY_SLUG


@pytest.mark.asyncio
async def test_unavailable_football_rewrite_uses_deterministic_market_lead(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    football_edition = tmp_path / "football.json"
    football_edition.write_text(
        json.dumps(
            {
                "edition_date": "2026-10-30",
                "coverage_date": "2026-10-29",
                "generated_at": "2026-10-30T08:00:00-04:00",
                "lead": {"headline": "National lead"},
                "scoreboard": [
                    {
                        "id": "1",
                        "completed": True,
                        "status": "Final",
                        "venue": "Lincoln Financial Field",
                        "away": {
                            "abbr": "NYG",
                            "name": "Giants",
                            "score": "17",
                            "winner": False,
                        },
                        "home": {
                            "abbr": "PHI",
                            "name": "Eagles",
                            "score": "24",
                            "winner": True,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    requested_dates: list[str] = []

    class UnavailableFootballService:
        async def generate(self, _game: dict, edition_date: str) -> None:
            requested_dates.append(edition_date)
            return None

    rendered: list[dict] = []
    monkeypatch.setattr(
        market_script, "MARKETS", (MARKETS_BY_SLUG["philadelphia"],)
    )
    monkeypatch.setattr(
        market_script,
        "render_football_page",
        lambda page, _output: rendered.append(page),
    )

    await market_script.generate(
        tmp_path / "missing-baseball.json",
        football_edition,
        tmp_path / "baseball-output",
        tmp_path / "football-output",
        football_service=UnavailableFootballService(),
        skip_baseball=True,
    )

    assert rendered[0]["lead"] is not None
    assert "Eagles" in rendered[0]["lead"]["headline"]
    assert requested_dates == ["2026-10-29"]

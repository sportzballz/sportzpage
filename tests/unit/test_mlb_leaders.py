from datetime import date

import pytest

from src.collectors.mlb import MLBCollector


@pytest.mark.asyncio
async def test_all_leaders_preserve_duplicate_categories_by_stat_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = MLBCollector(date(2026, 8, 27))

    async def fake_leaders(stat_group: str, category: str, _season: int) -> dict:
        return {"source": f"{stat_group}:{category}"}

    monkeypatch.setattr(collector, "get_stats_leaders", fake_leaders)

    leaders = await collector.get_all_leaders(2026)

    assert leaders["hitting:strikeOuts"]["source"] == "hitting:strikeOuts"
    assert leaders["pitching:strikeOuts"]["source"] == "pitching:strikeOuts"

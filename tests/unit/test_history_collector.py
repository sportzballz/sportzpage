import json
from datetime import date

from src.collectors.history import HistoryCollector
from src.normalization.normalizer import Normalizer

SAMPLE_HTML = """
<div class="mw-parser-output">
  <h2>Events</h2>
  <ul>
    <li>1920 - The first notable baseball event.</li>
    <li>1950 - The Philadelphia Phillies win a memorable game.</li>
    <li>1975 - Another league-wide milestone occurs.</li>
    <li>1984 - A major trade reshapes a contender.</li>
    <li>1999 - A record falls in dramatic fashion.</li>
    <li>2010 - A rookie makes his debut.</li>
    <li>2020 - The final event in the sample.</li>
  </ul>
  <h2>Births</h2>
  <ul><li>1980 - This must not be included.</li></ul>
</div>
"""


def test_builds_date_specific_baseball_reference_url():
    collector = HistoryCollector(date(2026, 8, 20))
    assert collector.source_url.endswith("/August_20")


def test_builds_collector_from_manifest_slug():
    collector = HistoryCollector.from_slug("October_31")
    assert collector.source_url.endswith("/October_31")


def test_parses_events_and_selects_five_with_phillies_priority():
    collector = HistoryCollector(date(2026, 8, 20))
    selected = collector.select_subset(collector.parse(SAMPLE_HTML))
    assert len(selected) == 5
    assert "Phillies" in selected[0]["description"]
    assert all("must not" not in event["description"] for event in selected)


def test_random_selection_is_stable_for_the_same_calendar_date():
    events = [
        {"year": 1900 + index, "description": f"League-wide event {index}."}
        for index in range(20)
    ]
    first = HistoryCollector(date(2025, 8, 20)).select_subset(events)
    second = HistoryCollector(date(2026, 8, 20)).select_subset(events)
    assert first == second


def test_normalizes_history_for_edition():
    normalized = Normalizer().normalize(
        {
            "history": {
                "source": "https://www.baseball-reference.com/bullpen/August_20",
                "items": [{"year": 1950, "description": "The Phillies won a memorable game."}],
            }
        }
    )
    assert normalized.historical_items[0].year == 1950
    assert normalized.historical_items[0].source.endswith("August_20")


async def test_local_database_is_curated_only_when_collected(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    days = tmp_path / "data" / "history" / "days"
    days.mkdir(parents=True)
    events = [
        {"year": 1900 + index, "description": f"League-wide event {index}."}
        for index in range(10)
    ]
    events[7]["description"] = "The Philadelphia Phillies make history."
    (days / "August_20.json").write_text(
        json.dumps({"source": "https://example.test/August_20", "items": events})
    )

    result = await HistoryCollector(date(2026, 8, 20)).collect()

    assert len(result["items"]) == 5
    assert "Phillies" in result["items"][0]["description"]

from src.pipeline.orchestrator import merge_schedules


def _schedule(date_value: str, *game_ids: int) -> dict:
    return {
        "copyright": "MLB",
        "totalGames": len(game_ids),
        "dates": [
            {
                "date": date_value,
                "games": [
                    {"gamePk": game_id, "status": {"detailedState": "Scheduled"}}
                    for game_id in game_ids
                ],
            }
        ],
    }


def test_merge_schedules_keeps_yesterday_and_all_of_today() -> None:
    merged = merge_schedules(
        _schedule("2026-08-20", 1, 2),
        _schedule("2026-08-21", 3, 4, 5),
    )

    assert merged["totalGames"] == 5
    assert [entry["date"] for entry in merged["dates"]] == ["2026-08-20", "2026-08-21"]
    assert [game["gamePk"] for game in merged["dates"][1]["games"]] == [3, 4, 5]


def test_merge_schedules_deduplicates_same_day_run() -> None:
    schedule = _schedule("2026-08-21", 3, 4, 5)

    merged = merge_schedules(schedule, schedule)

    assert merged["totalGames"] == 3
    assert len(merged["dates"]) == 1

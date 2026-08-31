import json
from pathlib import Path

from scripts.seed_lead_cache import seed, seed_football, seed_short_recaps
from src.models.story import GameRecap


def test_seeds_ai_lead_by_espn_game_id(tmp_path: Path) -> None:
    edition = tmp_path / "edition.json"
    edition.write_text(
        json.dumps(
            {
                "lead_story": {
                    "headline": "Cached lead",
                    "deck": "Cached deck",
                    "byline": "SportzBallz Staff",
                    "paragraphs": ["One.", "Two.", "Three."],
                    "source_data_references": ["game:123", "espn:401877087"],
                    "story_type": "lead",
                    "teams": ["ATL", "CWS"],
                    "facts_used": [
                        "home_runs:0",
                        "away_runs:2",
                        "espn_game_id:401877087",
                    ],
                    "ai_generated": True,
                    "source_name": "ESPN recap",
                    "source_url": "https://www.espn.com/mlb/recap/_/gameId/401877087",
                    "tags": [],
                    "players": [],
                }
            }
        ),
        encoding="utf-8",
    )

    cached = seed(edition, "2026-08-20", tmp_path / "cache")

    assert cached == tmp_path / "cache" / "2026-08-20-401877087.json"
    saved = json.loads(cached.read_text(encoding="utf-8"))
    assert saved["headline"] == "Cached lead"
    assert saved["game_id"] == 123
    assert saved["final_score"] == "ATL 2, CWS 0"
    assert GameRecap.model_validate(saved).ai_generated is True


def test_does_not_seed_short_market_brief_as_full_lead(tmp_path: Path) -> None:
    edition = tmp_path / "edition.json"
    edition.write_text(
        json.dumps(
            {
                "games": [{"game_id": 123, "game_date": "2026-08-20"}],
                "lead_story": {
                    "headline": "Short promoted brief",
                    "paragraphs": ["Only one paragraph."],
                    "ai_generated": True,
                    "source_data_references": ["game:123", "espn:401877087"],
                },
            }
        ),
        encoding="utf-8",
    )

    assert seed(edition, "2026-08-20", tmp_path / "cache") is None
    assert not (tmp_path / "cache/2026-08-20-401877087.json").exists()


def test_seeds_published_short_recaps(tmp_path: Path) -> None:
    edition = tmp_path / "edition.json"
    edition.write_text(
        json.dumps(
            {
                "lead_story": {
                    "source_data_references": ["game:1", "espn:lead"],
                    "ai_generated": True,
                },
                "games": [{"game_id": 2, "game_date": "2026-08-21"}],
                "game_recaps": [
                    {
                        "headline": "Short headline",
                        "deck": "Short deck",
                        "byline": "SportzBallz Staff",
                        "paragraphs": ["Two sentences make this brief. The finish had bite."],
                        "source_data_references": ["game:2", "espn:secondary"],
                        "story_type": "game_recap",
                        "teams": ["NYY", "BAL"],
                        "facts_used": ["espn_game_id:secondary"],
                        "ai_generated": True,
                        "source_name": "ESPN recap",
                        "source_url": "https://www.espn.com/mlb/recap/_/gameId/secondary",
                        "game_id": 2,
                        "final_score": "NYY 6, BAL 1",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    seeded = seed_short_recaps(edition, "2026-08-20", tmp_path / "cache")

    assert [path.name for path in seeded] == ["2026-08-21-secondary-short.json"]
    assert GameRecap.model_validate_json(seeded[0].read_text()).ai_generated is True


def test_seeds_published_football_lead(tmp_path: Path) -> None:
    edition = tmp_path / "football-edition.json"
    edition.write_text(
        json.dumps(
            {
                "edition_date": "2026-08-20",
                "lead": {
                    "headline": "Cached Eagles lead",
                    "deck": "Cached deck",
                    "paragraphs": ["One.", "Two.", "Three."],
                    "ai_generated": True,
                    "espn_game_id": "401",
                    "edition_date": "2026-08-20",
                },
            }
        ),
        encoding="utf-8",
    )

    cached = seed_football(edition, tmp_path / "cache")

    assert cached == tmp_path / "cache" / "nfl-2026-08-20-401.json"
    assert json.loads(cached.read_text())["headline"] == "Cached Eagles lead"

import json
from pathlib import Path

from scripts.seed_lead_cache import seed
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

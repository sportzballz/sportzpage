#!/usr/bin/env python3
"""Seed the daily lead-story cache from an already published edition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.models.story import GameRecap


def seed(edition_path: Path, game_date: str, cache_dir: Path) -> Path | None:
    if not edition_path.exists():
        return None
    edition = json.loads(edition_path.read_text(encoding="utf-8"))
    story = edition.get("lead_story") or {}
    if not story.get("ai_generated"):
        return None
    references = story.get("source_data_references") or []
    game_reference = next((value for value in references if value.startswith("game:")), None)
    facts = {
        key: value
        for fact in story.get("facts_used") or []
        if ":" in fact
        for key, value in [fact.split(":", 1)]
    }
    teams = story.get("teams") or []
    away_runs = int(facts.get("away_runs", 0))
    home_runs = int(facts.get("home_runs", 0))
    if len(teams) >= 2:
        away, home = teams[:2]
        winner, loser = (home, away) if home_runs > away_runs else (away, home)
        winning_runs, losing_runs = max(home_runs, away_runs), min(home_runs, away_runs)
        final_score = f"{winner} {winning_runs}, {loser} {losing_runs}"
    else:
        final_score = "Final"
    story.setdefault("game_id", int(game_reference.split(":", 1)[1]) if game_reference else 0)
    story.setdefault("final_score", final_score)
    recap = GameRecap.model_validate(story)
    espn_reference = next(
        (
            reference
            for reference in references
            if reference.startswith("espn:")
        ),
        None,
    )
    if not espn_reference:
        return None
    espn_game_id = espn_reference.split(":", 1)[1]
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / f"{game_date}-{espn_game_id}.json"
    if not destination.exists():
        destination.write_text(recap.model_dump_json(indent=2) + "\n", encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("edition", type=Path)
    parser.add_argument("--game-date", required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("build/ai-cache"))
    args = parser.parse_args()
    seeded = seed(args.edition, args.game_date, args.cache_dir)
    print(f"Seeded {seeded}" if seeded else "No reusable AI lead story found")


if __name__ == "__main__":
    main()

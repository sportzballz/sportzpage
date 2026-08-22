#!/usr/bin/env python3
"""Seed daily AI story caches from an already published edition."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def seed(edition_path: Path, game_date: str, cache_dir: Path) -> Path | None:
    if not edition_path.exists():
        return None
    edition = json.loads(edition_path.read_text(encoding="utf-8"))
    game_dates = {
        int(game["game_id"]): str(game.get("game_date") or game_date)
        for game in edition.get("games") or []
        if game.get("game_id") is not None
    }
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
    story_date = game_dates.get(int(story.get("game_id", 0)), game_date)
    destination = cache_dir / f"{story_date}-{espn_game_id}.json"
    if not destination.exists():
        destination.write_text(json.dumps(story, indent=2) + "\n", encoding="utf-8")
    return destination


def seed_short_recaps(edition_path: Path, game_date: str, cache_dir: Path) -> list[Path]:
    """Restore each already-published AI short recap for a fresh workflow runner."""
    if not edition_path.exists():
        return []
    edition = json.loads(edition_path.read_text(encoding="utf-8"))
    game_dates = {
        int(game["game_id"]): str(game.get("game_date") or game_date)
        for game in edition.get("games") or []
        if game.get("game_id") is not None
    }
    lead_references = (edition.get("lead_story") or {}).get("source_data_references") or []
    lead_espn_id = next(
        (ref.split(":", 1)[1] for ref in lead_references if ref.startswith("espn:")),
        None,
    )
    seeded: list[Path] = []
    for recap in edition.get("game_recaps") or []:
        if not recap.get("ai_generated"):
            continue
        references = recap.get("source_data_references") or []
        espn_id = next(
            (ref.split(":", 1)[1] for ref in references if ref.startswith("espn:")),
            None,
        )
        if not espn_id or espn_id == lead_espn_id:
            continue
        recap_date = game_dates.get(int(recap.get("game_id", 0)), game_date)
        destination = cache_dir / f"{recap_date}-{espn_id}-short.json"
        cache_dir.mkdir(parents=True, exist_ok=True)
        if not destination.exists():
            destination.write_text(json.dumps(recap, indent=2) + "\n", encoding="utf-8")
        seeded.append(destination)
    return seeded


def seed_football(edition_path: Path, cache_dir: Path) -> Path | None:
    """Restore the already-published AI football lead for a fresh runner."""
    if not edition_path.exists():
        return None
    edition = json.loads(edition_path.read_text(encoding="utf-8"))
    lead = edition.get("lead") or {}
    if not lead.get("ai_generated") or not lead.get("espn_game_id"):
        return None
    edition_date = str(lead.get("edition_date") or edition.get("edition_date") or "")[:10]
    if not edition_date:
        return None
    cache_dir.mkdir(parents=True, exist_ok=True)
    destination = cache_dir / f"nfl-{edition_date}-{lead['espn_game_id']}.json"
    if not destination.exists():
        destination.write_text(json.dumps(lead, indent=2) + "\n", encoding="utf-8")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("edition", type=Path)
    parser.add_argument("--game-date", required=True)
    parser.add_argument("--cache-dir", type=Path, default=Path("build/ai-cache"))
    parser.add_argument("--football-edition", type=Path)
    args = parser.parse_args()
    lead = seed(args.edition, args.game_date, args.cache_dir)
    recaps = seed_short_recaps(args.edition, args.game_date, args.cache_dir)
    football = (
        seed_football(args.football_edition, args.cache_dir)
        if args.football_edition
        else None
    )
    if lead:
        print(f"Seeded {lead}")
    for recap in recaps:
        print(f"Seeded {recap}")
    if football:
        print(f"Seeded {football}")
    if not lead and not recaps and not football:
        print("No reusable AI stories found")


if __name__ == "__main__":
    main()

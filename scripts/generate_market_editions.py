from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import date, datetime
from pathlib import Path

from src.editorial.espn_recap import ESPNLeadStoryService
from src.football.ai_recap import FootballLeadStoryService
from src.football.generator import render_football_page
from src.market_editions import (
    baseball_headline_game,
    football_headline_game,
    marketize_baseball,
    marketize_football,
)
from src.markets import MARKETS
from src.models.edition import Edition
from src.rendering.html_renderer import HTMLRenderer


async def generate(
    baseball_edition: Path,
    football_edition: Path,
    baseball_output: Path,
    football_output: Path,
    baseball_service: ESPNLeadStoryService | None = None,
    football_service: FootballLeadStoryService | None = None,
) -> None:
    base = Edition.model_validate_json(baseball_edition.read_text())
    football = json.loads(football_edition.read_text())
    football["edition_date"] = date.fromisoformat(football["edition_date"])
    football["generated_at"] = datetime.fromisoformat(football["generated_at"])
    renderer = HTMLRenderer.from_config()

    if baseball_service is None and os.getenv("AI_PROVIDER") == "openai":
        baseball_service = ESPNLeadStoryService(
            provider="openai", model=os.getenv("AI_MODEL") or "gpt-5-mini"
        )
    if football_service is None and os.getenv("AI_PROVIDER") == "openai":
        football_service = FootballLeadStoryService()

    for market in MARKETS:
        baseball_game = baseball_headline_game(base, market)
        baseball_lead = (
            await baseball_service.generate(baseball_game)
            if baseball_service and baseball_game
            else None
        )
        localized = marketize_baseball(base, market, baseball_lead)
        baseball_dir = baseball_output / market.slug
        baseball_dir.mkdir(parents=True, exist_ok=True)
        (baseball_dir / "edition.json").write_text(localized.model_dump_json(indent=2))
        (baseball_dir / "index.html").write_text(renderer.render(localized))

        football_game = football_headline_game(football, market)
        football_lead = (
            await football_service.generate(football_game, football["edition_date"].isoformat())
            if football_service and football_game
            else None
        )
        football_dir = football_output / market.slug
        render_football_page(marketize_football(football, market, football_lead), football_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseball-edition", type=Path, default=Path("build/edition.json"))
    parser.add_argument(
        "--football-edition", type=Path, default=Path("build/football/edition.json")
    )
    parser.add_argument("--baseball-output", type=Path, default=Path("build/markets"))
    parser.add_argument(
        "--football-output", type=Path, default=Path("build/football-markets")
    )
    args = parser.parse_args()
    asyncio.run(
        generate(
            args.baseball_edition,
            args.football_edition,
            args.baseball_output,
            args.football_output,
        )
    )


if __name__ == "__main__":
    main()

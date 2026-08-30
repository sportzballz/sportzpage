from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from src.football.generator import render_football_page
from src.market_editions import marketize_baseball, marketize_football
from src.markets import MARKETS
from src.models.edition import Edition
from src.rendering.html_renderer import HTMLRenderer


def generate(
    baseball_edition: Path,
    football_edition: Path,
    baseball_output: Path,
    football_output: Path,
) -> None:
    base = Edition.model_validate_json(baseball_edition.read_text())
    football = json.loads(football_edition.read_text())
    football["edition_date"] = date.fromisoformat(football["edition_date"])
    football["generated_at"] = datetime.fromisoformat(football["generated_at"])
    renderer = HTMLRenderer.from_config()

    for market in MARKETS:
        localized = marketize_baseball(base, market)
        baseball_dir = baseball_output / market.slug
        baseball_dir.mkdir(parents=True, exist_ok=True)
        (baseball_dir / "edition.json").write_text(localized.model_dump_json(indent=2))
        (baseball_dir / "index.html").write_text(renderer.render(localized))

        football_dir = football_output / market.slug
        render_football_page(marketize_football(football, market), football_dir)


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
    generate(
        args.baseball_edition,
        args.football_edition,
        args.baseball_output,
        args.football_output,
    )


if __name__ == "__main__":
    main()

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.markets import DEFAULT_MARKET, MARKETS
from src.nba.ai_recap import NBALeadStoryService
from src.rendering.edition_meta import daypart_edition, format_eastern_time, volume_number

EASTERN = ZoneInfo("America/New_York")
BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"
STANDINGS = "https://site.web.api.espn.com/apis/v2/sports/basketball/nba/standings"
BASKETBALL_TEAMS = {
    "philadelphia": ("PHI",),
    "boston": ("BOS",),
    "new-york": ("NY", "BKN"),
    "los-angeles": ("LAL", "LAC"),
    "chicago": ("CHI",),
    "dallas": ("DAL",),
}


def _games(payload: dict[str, Any]) -> list[dict[str, Any]]:
    games: list[dict[str, Any]] = []
    for event in payload.get("events") or []:
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        home = next((team for team in competitors if team.get("homeAway") == "home"), None)
        away = next((team for team in competitors if team.get("homeAway") == "away"), None)
        if not home or not away or not event.get("date"):
            continue
        start = datetime.fromisoformat(str(event["date"]).replace("Z", "+00:00"))
        status = (event.get("status") or {}).get("type") or {}

        def team(value: dict[str, Any]) -> dict[str, str]:
            details = value.get("team") or {}
            return {
                "name": str(
                    details.get("displayName") or details.get("shortDisplayName") or "Team"
                ),
                "abbreviation": str(details.get("abbreviation") or ""),
                "score": str(value.get("score") or "0"),
            }

        games.append(
            {
                "id": str(event.get("id") or ""),
                "date": start.astimezone(EASTERN).date().isoformat(),
                "time": start.astimezone(EASTERN).strftime("%-I:%M %p ET"),
                "status": str(
                    status.get("shortDetail") or status.get("description") or "Scheduled"
                ),
                "completed": bool(status.get("completed")),
                "away": team(away),
                "home": team(home),
                "venue": str((competition.get("venue") or {}).get("fullName") or ""),
            }
        )
    return games


def _standings(payload: dict[str, Any]) -> list[dict[str, Any]]:
    conferences: list[dict[str, Any]] = []
    for conference in payload.get("children") or []:
        entries = (conference.get("standings") or {}).get("entries") or []
        if not entries:
            entries = [
                entry
                for division in conference.get("children") or []
                for entry in (division.get("standings") or {}).get("entries") or []
            ]
        rows = []
        for entry in entries:
            stats = {
                stat.get("name"): stat.get("displayValue", "")
                for stat in entry.get("stats") or []
            }
            team = entry.get("team") or {}
            seed_text = str(stats.get("playoffSeed", "99"))
            seed = int(seed_text) if seed_text.isdigit() else 99
            rows.append(
                {
                    "team": team.get("displayName") or team.get("name") or "Team",
                    "w": stats.get("wins", "0"),
                    "l": stats.get("losses", "0"),
                    "pct": stats.get("winPercent", stats.get("winPercentage", ".000")),
                    "gb": stats.get("gamesBehind", "—"),
                    "streak": stats.get("streak", "—"),
                    "seed": seed,
                }
            )
        if rows:
            rows.sort(key=lambda row: row["seed"])
            for row in rows:
                row.pop("seed", None)
            conferences.append(
                {"name": conference.get("name") or "Conference", "rows": rows}
            )
    return conferences


def _news_candidates(
    payload: dict[str, Any], abbreviations: tuple[str, ...]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for article in payload.get("articles") or []:
        api_url = (((article.get("links") or {}).get("api") or {}).get("self") or {}).get(
            "href"
        )
        if not api_url or not str(api_url).startswith("https://content.core.api.espn.com/"):
            continue
        teams = [
            str(team.get("abbreviation") or "")
            for team in article.get("categories") or []
            if team.get("type") == "team"
        ]
        candidates.append(
            {
                "id": str(article.get("id") or ""),
                "headline": str(article.get("headline") or ""),
                "description": str(article.get("description") or ""),
                "api_url": str(api_url),
                "local": bool(set(teams) & set(abbreviations)),
            }
        )
    return sorted(candidates, key=lambda item: not item["local"])


async def _get(client: httpx.AsyncClient, url: str, params: dict[str, str]) -> dict[str, Any]:
    try:
        response = await client.get(url, params=params)
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except (httpx.HTTPError, ValueError):
        return {}


async def generate(edition_date: date, build_dir: Path) -> None:
    async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
        yesterday, today, tomorrow, standings, news = await asyncio.gather(
            _get(
                client,
                f"{BASE}/scoreboard",
                {"dates": (edition_date - timedelta(days=1)).strftime("%Y%m%d")},
            ),
            _get(client, f"{BASE}/scoreboard", {"dates": edition_date.strftime("%Y%m%d")}),
            _get(
                client,
                f"{BASE}/scoreboard",
                {"dates": (edition_date + timedelta(days=1)).strftime("%Y%m%d")},
            ),
            _get(
                client,
                STANDINGS,
                {"region": "us", "lang": "en", "contentorigin": "espn", "type": "0", "level": "2"},
            ),
            _get(client, f"{BASE}/news", {"limit": "100"}),
        )
    yesterday_games = _games(yesterday)
    today_games = _games(today)
    tomorrow_games = _games(tomorrow)
    all_games = yesterday_games + today_games + tomorrow_games
    service = NBALeadStoryService() if os.getenv("AI_PROVIDER", "").casefold() == "openai" else None
    conferences = _standings(standings)
    environment = Environment(
        loader=FileSystemLoader("templates"), autoescape=select_autoescape(["html", "j2"])
    )
    environment.globals.update(
        cloudflare_web_analytics_token=os.getenv("CLOUDFLARE_WEB_ANALYTICS_TOKEN", ""),
        format_eastern_time=format_eastern_time,
        daypart_edition=daypart_edition,
        volume_number=volume_number,
        markets=MARKETS,
    )
    template = environment.get_template("nba.html.j2")
    national_lead: dict[str, Any] | None = None
    national_searched = False
    for market in MARKETS:
        local = BASKETBALL_TEAMS[market.slug]
        local_games = [
            game
            for game in all_games
            if game["away"]["abbreviation"] in local or game["home"]["abbreviation"] in local
        ]
        lead = None
        if service:
            for game in reversed(local_games):
                if game["completed"]:
                    lead = await service.generate(game, edition_date.isoformat())
                    if lead:
                        break
            if not lead:
                for article in _news_candidates(news, local):
                    if not article["local"]:
                        break
                    lead = await service.generate_from_news(article, edition_date.isoformat())
                    if lead:
                        break
            if not lead:
                if not national_searched:
                    national_searched = True
                    for article in _news_candidates(news, ()):
                        national_lead = await service.generate_from_news(
                            article, edition_date.isoformat()
                        )
                        if national_lead:
                            break
                lead = national_lead
        page = {
            "edition_date": edition_date,
            "generated_at": datetime.now(EASTERN),
            "market_slug": market.slug,
            "market_label": market.label,
            "canonical_path": "/nba/"
            if market.slug == DEFAULT_MARKET.slug
            else f"/editions/{market.slug}/nba/",
            "lead": lead,
            "games": today_games,
            "recent_games": yesterday_games,
            "upcoming_games": tomorrow_games,
            "conferences": conferences,
        }
        destination = build_dir / market.slug
        destination.mkdir(parents=True, exist_ok=True)
        (destination / "edition.json").write_text(
            json.dumps(page, default=str, indent=2) + "\n", encoding="utf-8"
        )
        (destination / "index.html").write_text(template.render(page=page), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, default=datetime.now(EASTERN).date())
    parser.add_argument("--build-dir", type=Path, default=Path("build/nba-markets"))
    args = parser.parse_args()
    asyncio.run(generate(args.date, args.build_dir))


if __name__ == "__main__":
    main()

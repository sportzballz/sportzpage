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
from src.nhl.ai_recap import NHLLeadStoryService
from src.rendering.edition_meta import daypart_edition, format_eastern_time, volume_number

EASTERN = ZoneInfo("America/New_York")
BASE = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl"
STANDINGS = "https://site.web.api.espn.com/apis/v2/sports/hockey/nhl/standings"
HOCKEY_TEAMS = {
    "philadelphia": ("PHI",),
    "boston": ("BOS",),
    "new-york": ("NYR", "NYI", "NJ"),
    "los-angeles": ("LA", "ANA"),
    "chicago": ("CHI",),
    "dallas": ("DAL",),
}


def _games(payload: dict[str, Any]) -> list[dict[str, Any]]:
    games = []
    for event in payload.get("events") or []:
        competition = (event.get("competitions") or [{}])[0]
        competitors = competition.get("competitors") or []
        home = next((c for c in competitors if c.get("homeAway") == "home"), None)
        away = next((c for c in competitors if c.get("homeAway") == "away"), None)
        if not home or not away:
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
    divisions = []
    for conference in payload.get("children") or []:
        for division in conference.get("children") or []:
            rows = []
            for entry in (division.get("standings") or {}).get("entries") or []:
                stats = {
                    stat.get("name"): stat.get("displayValue", "")
                    for stat in entry.get("stats") or []
                }
                team = entry.get("team") or {}
                rows.append(
                    {
                        "team": team.get("displayName") or team.get("name") or "Team",
                        "gp": stats.get("gamesPlayed", "0"),
                        "w": stats.get("wins", "0"),
                        "l": stats.get("losses", "0"),
                        "otl": stats.get("otLosses", "0"),
                        "pts": stats.get("points", "0"),
                    }
                )
            divisions.append({"name": division.get("name") or "Division", "rows": rows})
    return divisions


def _news_candidates(
    payload: dict[str, Any], abbreviations: tuple[str, ...]
) -> list[dict[str, str]]:
    candidates = []
    for article in payload.get("articles") or []:
        api_url = (((article.get("links") or {}).get("api") or {}).get("self") or {}).get("href")
        if not api_url or not str(api_url).startswith("https://content.core.api.espn.com/"):
            continue
        teams = [
            str(team.get("abbreviation") or "")
            for team in article.get("categories") or []
            if team.get("type") == "team"
        ]
        headline = str(article.get("headline") or "")
        candidates.append(
            {
                "id": str(article.get("id") or ""),
                "headline": headline,
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
        return response.json()
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
                {"region": "us", "lang": "en", "contentorigin": "espn", "type": "0", "level": "3"},
            ),
            _get(client, f"{BASE}/news", {"limit": "100"}),
        )
    games = _games(yesterday) + _games(today) + _games(tomorrow)
    service = NHLLeadStoryService() if os.getenv("AI_PROVIDER", "").casefold() == "openai" else None
    divisions = _standings(standings)
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
    template = environment.get_template("nhl.html.j2")
    national_lead: dict[str, Any] | None = None
    national_searched = False
    for market in MARKETS:
        local = HOCKEY_TEAMS[market.slug]
        local_games = [
            game
            for game in games
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
            "canonical_path": "/nhl/"
            if market.slug == DEFAULT_MARKET.slug
            else f"/editions/{market.slug}/nhl/",
            "lead": lead,
            "games": _games(today),
            "recent_games": _games(yesterday),
            "upcoming_games": _games(tomorrow),
            "divisions": divisions,
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
    parser.add_argument("--build-dir", type=Path, default=Path("build/nhl-markets"))
    args = parser.parse_args()
    asyncio.run(generate(args.date, args.build_dir))


if __name__ == "__main__":
    main()

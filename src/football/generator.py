from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from jinja2 import Environment, FileSystemLoader, select_autoescape

from src.football.ai_recap import FootballLeadStoryService
from src.markets import DEFAULT_MARKET, MARKETS
from src.rendering.edition_meta import daypart_edition, format_eastern_time, volume_number

EASTERN = ZoneInfo("America/New_York")
SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
STANDINGS_URL = "https://site.web.api.espn.com/apis/v2/sports/football/nfl/standings"
NEWS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/news"
LEADERS_URL = "https://site.api.espn.com/apis/site/v3/sports/football/nfl/leaders"
NFC_EAST = {"PHI", "DAL", "NYG", "WSH"}
LEADER_CATEGORIES = (
    "passingYards",
    "rushingYards",
    "receivingYards",
    "totalTackles",
    "sacks",
    "interceptions",
)


def render_football_page(data: dict[str, Any], output_dir: Path) -> Path:
    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals["cloudflare_web_analytics_token"] = os.getenv(
        "CLOUDFLARE_WEB_ANALYTICS_TOKEN", ""
    )
    env.globals["format_eastern_time"] = format_eastern_time
    env.globals["daypart_edition"] = daypart_edition
    env.globals["volume_number"] = volume_number
    env.globals["markets"] = MARKETS
    html = env.get_template("football.html.j2").render(page=data)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "edition.json").write_text(json.dumps(data, default=str, indent=2))
    path = output_dir / "index.html"
    path.write_text(html)
    return path


@dataclass
class FootballEditionGenerator:
    edition_date: date
    timeout: float = 20.0
    lead_story_service: FootballLeadStoryService | None = None

    def __post_init__(self) -> None:
        if self.lead_story_service is None and os.getenv("AI_PROVIDER") == "openai":
            self.lead_story_service = FootballLeadStoryService(timeout=self.timeout + 25)

    async def collect(self) -> dict[str, Any]:
        today = datetime.now(EASTERN).date()
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            edition_scoreboard = await self._get(
                client, SCOREBOARD_URL, {"dates": self.edition_date.strftime("%Y%m%d")}
            )
            week = self._week_context(edition_scoreboard)
            weekly_params = {"dates": str(week["season_year"])}
            if week["season_type"] and week["number"]:
                weekly_params.update(
                    {"seasontype": str(week["season_type"]), "week": str(week["number"])}
                )
            weekly, standings, news, leaders = await asyncio.gather(
                self._get(client, SCOREBOARD_URL, weekly_params),
                self._get(client, STANDINGS_URL, {"region": "us", "lang": "en", "contentorigin": "espn", "type": "0", "level": "3"}),
                self._get(client, NEWS_URL, {"limit": "10"}),
                self._get_optional(client, LEADERS_URL, {}),
            )
        previous_games = self._games(edition_scoreboard)
        weekly_games = self._games(weekly)
        for game in weekly_games:
            game["is_today"] = game["date"] == today.isoformat()
        lead_game = self._select_lead_game(previous_games)
        lead = self._lead_story(lead_game) if lead_game else None
        if lead_game and self.lead_story_service:
            lead = await self.lead_story_service.generate(
                lead_game, self.edition_date.isoformat()
            ) or lead
        return {
            "generated_at": datetime.now(EASTERN),
            "edition_date": self.edition_date,
            "season_label": week["season_label"],
            "week_label": week["label"],
            "week_detail": week["detail"],
            "market_slug": DEFAULT_MARKET.slug,
            "market_label": DEFAULT_MARKET.label,
            "market_teams": list(DEFAULT_MARKET.football_teams),
            "canonical_path": "/football/",
            "lead": lead,
            "scoreboard": weekly_games,
            "standings": self._standings(standings),
            "league_leaders": self._league_leaders(leaders),
            "leaders_season_label": self._leaders_season_label(leaders),
            "news": self._news(news),
        }

    async def _get(self, client: httpx.AsyncClient, url: str, params: dict[str, str]) -> dict[str, Any]:
        response = await client.get(
            url,
            params=params,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "application/json,text/plain,*/*",
            },
        )
        response.raise_for_status()
        return response.json()

    async def _get_optional(
        self, client: httpx.AsyncClient, url: str, params: dict[str, str]
    ) -> dict[str, Any]:
        try:
            return await self._get(client, url, params)
        except (httpx.HTTPError, ValueError):
            return {}

    @staticmethod
    def _games(payload: dict[str, Any]) -> list[dict[str, Any]]:
        games: list[dict[str, Any]] = []
        for event in payload.get("events", []):
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors") or []
            by_side = {c.get("homeAway"): c for c in competitors}
            away, home = by_side.get("away", {}), by_side.get("home", {})
            status = (competition.get("status") or event.get("status") or {}).get("type", {})
            venue = (competition.get("venue") or {}).get("fullName", "Venue TBA")
            start = event.get("date")
            start_et = datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(EASTERN) if start else None
            odds = (competition.get("odds") or [{}])[0]
            games.append({
                "id": str(event.get("id", "")),
                "name": event.get("name", "NFL game"),
                "away": FootballEditionGenerator._team(away),
                "home": FootballEditionGenerator._team(home),
                "status": status.get("description", "Scheduled"),
                "completed": bool(status.get("completed")),
                "detail": status.get("shortDetail") or status.get("detail") or "",
                "date": start_et.date().isoformat() if start_et else "",
                "date_label": start_et.strftime("%a, %b %-d") if start_et else "Date TBA",
                "time": start_et.strftime("%-I:%M %p ET") if start_et else "TBA",
                "venue": venue,
                "broadcast": ", ".join(competition.get("broadcasts", [{}])[0].get("names", [])) if competition.get("broadcasts") else "",
                "odds": odds.get("details") or odds.get("spread") or "",
                "over_under": odds.get("overUnder"),
                "recap_url": f"https://www.espn.com/nfl/recap/_/gameId/{event.get('id')}",
            })
        return games

    @staticmethod
    def _week_context(payload: dict[str, Any]) -> dict[str, Any]:
        league = (payload.get("leagues") or [{}])[0]
        season = league.get("season") or {}
        season_type = season.get("type") or {}
        number = (payload.get("week") or {}).get("number")
        label = f"Week {number}" if number else "NFL Schedule"
        detail = ""
        for period in league.get("calendar") or []:
            if str(period.get("value")) != str(season_type.get("id")):
                continue
            for entry in period.get("entries") or []:
                if str(entry.get("value")) == str(number):
                    label = entry.get("label") or label
                    detail = entry.get("detail") or ""
                    break
        return {
            "season_year": season.get("year") or datetime.now(EASTERN).year,
            "season_type": season_type.get("id"),
            "season_label": season_type.get("name", "NFL"),
            "number": number,
            "label": label,
            "detail": detail,
        }

    @staticmethod
    def _team(competitor: dict[str, Any]) -> dict[str, Any]:
        team = competitor.get("team") or {}
        return {
            "abbr": team.get("abbreviation", "TBA"),
            "name": team.get("displayName", team.get("name", "TBA")),
            "score": competitor.get("score", "0"),
            "record": ((competitor.get("records") or [{}])[0]).get("summary", ""),
            "winner": competitor.get("winner", False),
        }

    @staticmethod
    def _select_lead(games: list[dict[str, Any]]) -> dict[str, Any] | None:
        game = FootballEditionGenerator._select_lead_game(games)
        return FootballEditionGenerator._lead_story(game) if game else None

    @staticmethod
    def _select_lead_game(games: list[dict[str, Any]]) -> dict[str, Any] | None:
        completed = [game for game in games if game["completed"]]
        for teams in ({"PHI"}, NFC_EAST):
            match = next((game for game in completed if {game["away"]["abbr"], game["home"]["abbr"]} & teams), None)
            if match:
                return match
        return completed[0] if completed else None

    @staticmethod
    def _lead_story(
        game: dict[str, Any], market_label: str = "Philadelphia"
    ) -> dict[str, Any]:
        away, home = game["away"], game["home"]
        winner = away if away["winner"] else home
        loser = home if winner is away else away
        return {
            "headline": f"{winner['name']} Take the Day, {winner['score']}-{loser['score']}",
            "deck": f"{winner['abbr']} finished ahead of {loser['abbr']} in {game['status'].lower()} action at {game['venue']}.",
            "paragraphs": [
                f"The {winner['name']} came away with a {winner['score']}-{loser['score']} result over the {loser['name']}, putting the defining score of the day at the top of The Daily Sports Page's football edition.",
                f"The game was played at {game['venue']}. The result offers an early checkpoint for both clubs as the NFL calendar moves toward the regular season.",
                f"The {market_label} edition follows its local clubs first while keeping the full NFL slate in view.",
            ],
            "url": game["recap_url"],
            "ai_generated": False,
            "espn_game_id": str(game["id"]),
            "edition_date": "",
        }

    @staticmethod
    def _standings(payload: dict[str, Any]) -> list[dict[str, Any]]:
        groups: list[dict[str, Any]] = []
        root = (payload.get("children") or [])
        for conference in root:
            for division in conference.get("children", []):
                rows = []
                for entry in ((division.get("standings") or {}).get("entries") or []):
                    stats = {s.get("name"): s.get("displayValue") for s in entry.get("stats", [])}
                    team = entry.get("team") or {}
                    rows.append({
                        "abbr": team.get("abbreviation", ""),
                        "name": team.get("displayName", ""),
                        "wins": stats.get("wins", "0"),
                        "losses": stats.get("losses", "0"),
                        "ties": stats.get("ties", "0"),
                        "pct": stats.get("winPercent", ".000"),
                        "diff": stats.get("pointDifferential", "0"),
                    })
                if rows:
                    groups.append({"name": division.get("name", "Division"), "rows": rows})
        return groups

    @staticmethod
    def _news(payload: dict[str, Any]) -> list[dict[str, str]]:
        stories = []
        for article in payload.get("articles", []):
            link = (article.get("links", {}).get("web", {}) or {}).get("href", "")
            stories.append({"headline": article.get("headline", "NFL notebook"), "description": article.get("description", ""), "url": link})
        return stories[:8]

    @staticmethod
    def _league_leaders(payload: dict[str, Any]) -> list[dict[str, Any]]:
        categories = {
            category.get("name"): category
            for category in (payload.get("leaders") or {}).get("categories", [])
        }
        result: list[dict[str, Any]] = []
        for category_name in LEADER_CATEGORIES:
            category = categories.get(category_name)
            if not category:
                continue
            rows = []
            for rank, leader in enumerate(category.get("leaders") or [], start=1):
                athlete = leader.get("athlete") or {}
                team = leader.get("team") or {}
                if not athlete.get("displayName"):
                    continue
                player_url = next(
                    (
                        link.get("href", "")
                        for link in athlete.get("links") or []
                        if "playercard" in (link.get("rel") or [])
                        and str(link.get("href", "")).startswith("https://")
                    ),
                    "",
                )
                rows.append(
                    {
                        "rank": rank,
                        "name": athlete["displayName"],
                        "position": (athlete.get("position") or {}).get("abbreviation", ""),
                        "team": team.get("abbreviation", ""),
                        "value": leader.get("displayValue", ""),
                        "url": player_url,
                    }
                )
                if len(rows) == 5:
                    break
            if rows:
                result.append(
                    {
                        "name": category_name,
                        "label": category.get("displayName", category_name),
                        "abbreviation": category.get("abbreviation", ""),
                        "rows": rows,
                    }
                )
        return result

    @staticmethod
    def _leaders_season_label(payload: dict[str, Any]) -> str:
        season = payload.get("requestedSeason") or payload.get("currentSeason") or {}
        season_type = season.get("type") or {}
        return " ".join(
            part
            for part in (str(season.get("year") or ""), season_type.get("name", ""))
            if part
        )

    async def generate(self, output_dir: Path) -> Path:
        data = await self.collect()
        return render_football_page(data, output_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument("--build-dir", type=Path, default=Path("build/football"))
    args = parser.parse_args()
    path = asyncio.run(FootballEditionGenerator(args.date).generate(args.build_dir))
    print(f"Football edition rendered to {path}")


if __name__ == "__main__":
    main()

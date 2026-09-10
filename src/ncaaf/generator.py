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

from src.markets import DEFAULT_MARKET, MARKETS
from src.ncaaf.ai_recap import NCAAFLeadStoryService
from src.rendering.edition_meta import daypart_edition, format_eastern_time, volume_number

EASTERN = ZoneInfo("America/New_York")
SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard"
)
STANDINGS_URL = "https://site.web.api.espn.com/apis/v2/sports/football/college-football/standings"
RANKINGS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/rankings"
NEWS_URL = "https://site.api.espn.com/apis/site/v2/sports/football/college-football/news"
FBS_GROUP = "80"
MAJOR_CONFERENCES = {
    "1": "ACC",
    "4": "Big 12",
    "5": "Big Ten",
    "8": "SEC",
    "9": "Pac-12",
}


def render_ncaaf_page(data: dict[str, Any], output_dir: Path) -> Path:
    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.globals.update(
        cloudflare_web_analytics_token=os.getenv("CLOUDFLARE_WEB_ANALYTICS_TOKEN", ""),
        format_eastern_time=format_eastern_time,
        daypart_edition=daypart_edition,
        volume_number=volume_number,
        markets=MARKETS,
    )
    html = env.get_template("ncaaf.html.j2").render(page=data)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "edition.json").write_text(json.dumps(data, default=str, indent=2))
    path = output_dir / "index.html"
    path.write_text(html)
    return path


@dataclass
class NCAAFEditionGenerator:
    edition_date: date
    timeout: float = 20.0
    lead_story_service: NCAAFLeadStoryService | None = None

    def __post_init__(self) -> None:
        if self.lead_story_service is None and os.getenv("AI_PROVIDER", "").casefold() == "openai":
            self.lead_story_service = NCAAFLeadStoryService(timeout=self.timeout + 25)

    async def collect(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            daily, standings, rankings, news = await asyncio.gather(
                self._get_optional(
                    client,
                    SCOREBOARD_URL,
                    {
                        "dates": self.edition_date.strftime("%Y%m%d"),
                        "groups": FBS_GROUP,
                        "limit": "200",
                    },
                ),
                self._get_optional(
                    client,
                    STANDINGS_URL,
                    {
                        "region": "us",
                        "lang": "en",
                        "contentorigin": "espn",
                        "type": "0",
                        "level": "3",
                    },
                ),
                self._get_optional(client, RANKINGS_URL, {}),
                self._get_optional(client, NEWS_URL, {"limit": "100"}),
            )
            week = self._week_context(daily, self.edition_date)
            weekly = await self._get_optional(
                client,
                SCOREBOARD_URL,
                {
                    "dates": str(week["season_year"]),
                    "seasontype": str(week["season_type"] or 2),
                    "week": str(week["number"] or ""),
                    "groups": FBS_GROUP,
                    "limit": "200",
                },
            )

        ranking_map, poll = self._rankings(rankings)
        games = self._games(weekly or daily, ranking_map)
        major_games = [game for game in games if game["major_conference"]]
        daily_games = [
            game for game in self._games(daily, ranking_map) if game["major_conference"]
        ]
        lead_game = self._select_lead_game(daily_games)
        lead = self._story_for_game(lead_game) if lead_game else None
        if lead_game and self.lead_story_service:
            generated = await self.lead_story_service.generate(
                lead_game, self.edition_date.isoformat()
            )
            if not generated:
                for news_item in self._news_candidates(news):
                    generated = await self.lead_story_service.generate_from_news(
                        news_item, self.edition_date.isoformat()
                    )
                    if generated:
                        break
            lead = generated or lead
        elif self.lead_story_service:
            for news_item in self._news_candidates(news):
                lead = await self.lead_story_service.generate_from_news(
                    news_item, self.edition_date.isoformat()
                )
                if lead:
                    break
        today = datetime.now(EASTERN).date().isoformat()
        for game in major_games:
            game["is_today"] = game["date"] == today
        return {
            "generated_at": datetime.now(EASTERN),
            "edition_date": self.edition_date,
            "season_label": week["season_label"],
            "week_label": week["label"],
            "week_detail": week["detail"],
            "market_slug": DEFAULT_MARKET.slug,
            "market_label": DEFAULT_MARKET.label,
            "canonical_path": "/ncaaf/",
            "lead": lead,
            "scoreboard": major_games,
            "rankings": poll,
            "conferences": self._conference_standings(standings),
        }

    async def _get_optional(
        self, client: httpx.AsyncClient, url: str, params: dict[str, str]
    ) -> dict[str, Any]:
        try:
            response = await client.get(
                url,
                params={key: value for key, value in params.items() if value},
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36"
                    ),
                    "Accept": "application/json,text/plain,*/*",
                },
            )
            response.raise_for_status()
            return response.json()
        except (httpx.HTTPError, ValueError):
            return {}

    @staticmethod
    def _week_context(payload: dict[str, Any], target_date: date) -> dict[str, Any]:
        league = (payload.get("leagues") or [{}])[0]
        season = league.get("season") or {}
        season_type = season.get("type") or {}
        number = (payload.get("week") or {}).get("number")
        label = f"Week {number}" if number else "College Football"
        detail = ""
        for period in league.get("calendar") or []:
            if str(period.get("value")) != str(season_type.get("id")):
                continue
            for entry in period.get("entries") or []:
                if number is None and entry.get("startDate") and entry.get("endDate"):
                    starts = datetime.fromisoformat(entry["startDate"].replace("Z", "+00:00"))
                    ends = datetime.fromisoformat(entry["endDate"].replace("Z", "+00:00"))
                    target = datetime.combine(
                        target_date, datetime.min.time(), EASTERN
                    ) + timedelta(hours=12)
                    if starts <= target.astimezone(starts.tzinfo) <= ends:
                        number = entry.get("value")
                if str(entry.get("value")) == str(number):
                    label = entry.get("label") or label
                    detail = entry.get("detail") or ""
                    break
        return {
            "season_year": season.get("year") or datetime.now(EASTERN).year,
            "season_type": season_type.get("id") or 2,
            "season_label": season_type.get("name", "Regular Season"),
            "number": number,
            "label": label,
            "detail": detail,
        }

    @staticmethod
    def _rankings(payload: dict[str, Any]) -> tuple[dict[str, int], list[dict[str, Any]]]:
        polls = payload.get("rankings") or []
        poll = next(
            (item for item in polls if "ap" in str(item.get("name", "")).casefold()),
            polls[0] if polls else {},
        )
        ranking_map: dict[str, int] = {}
        rows = []
        for entry in poll.get("ranks") or []:
            team = entry.get("team") or {}
            team_id = str(team.get("id") or "")
            rank = int(entry.get("current") or 0)
            if team_id and rank:
                ranking_map[team_id] = rank
            rows.append(
                {
                    "rank": rank,
                    "team": team.get("location") or team.get("displayName", ""),
                    "record": entry.get("recordSummary", ""),
                    "points": entry.get("points", ""),
                }
            )
        return ranking_map, rows[:25]

    @staticmethod
    def _games(payload: dict[str, Any], ranking_map: dict[str, int]) -> list[dict[str, Any]]:
        games = []
        for event in payload.get("events") or []:
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors") or []
            sides = {item.get("homeAway"): item for item in competitors}
            away, home = sides.get("away", {}), sides.get("home", {})
            status = (competition.get("status") or event.get("status") or {}).get("type", {})
            start = event.get("date")
            start_et = (
                datetime.fromisoformat(start.replace("Z", "+00:00")).astimezone(EASTERN)
                if start
                else None
            )

            def team(item: dict[str, Any]) -> dict[str, Any]:
                value = item.get("team") or {}
                team_id = str(value.get("id") or "")
                conference_id = str(value.get("conferenceId") or item.get("conferenceId") or "")
                curated = item.get("curatedRank") or {}
                rank = ranking_map.get(team_id) or int(curated.get("current") or 0)
                if rank > 25:
                    rank = 0
                return {
                    "id": team_id,
                    "abbr": value.get("abbreviation", "TBA"),
                    "name": value.get("location") or value.get("displayName", "TBA"),
                    "score": item.get("score", "0"),
                    "record": ((item.get("records") or [{}])[0]).get("summary", ""),
                    "winner": bool(item.get("winner")),
                    "rank": rank,
                    "conference": MAJOR_CONFERENCES.get(conference_id, ""),
                }

            away_team, home_team = team(away), team(home)
            broadcasts = competition.get("broadcasts") or []
            games.append(
                {
                    "id": str(event.get("id", "")),
                    "away": away_team,
                    "home": home_team,
                    "status": status.get("description", "Scheduled"),
                    "completed": bool(status.get("completed")),
                    "date": start_et.date().isoformat() if start_et else "",
                    "date_label": start_et.strftime("%a, %b %-d") if start_et else "Date TBA",
                    "time": start_et.strftime("%-I:%M %p ET") if start_et else "TBA",
                    "venue": (competition.get("venue") or {}).get("fullName", "Venue TBA"),
                    "broadcast": ", ".join(broadcasts[0].get("names", [])) if broadcasts else "",
                    "major_conference": bool(away_team["conference"] or home_team["conference"]),
                }
            )
        return games

    @staticmethod
    def _conference_standings(payload: dict[str, Any]) -> list[dict[str, Any]]:
        result = []
        for conference in payload.get("children") or []:
            conference_id = str(conference.get("id") or "")
            if conference_id not in MAJOR_CONFERENCES:
                continue
            rows = []
            for entry in (conference.get("standings") or {}).get("entries") or []:
                stats: dict[str, str] = {}
                for stat in entry.get("stats") or []:
                    stats.setdefault(str(stat.get("name")), str(stat.get("displayValue", "")))
                    stats.setdefault(str(stat.get("type")), str(stat.get("displayValue", "")))
                team = entry.get("team") or {}
                rows.append(
                    {
                        "rank": team.get("rank") or "",
                        "team": team.get("location") or team.get("shortDisplayName", ""),
                        "conference": stats.get(
                            "leagueRecord",
                            stats.get("conferenceRecord", stats.get("vsconf", "0-0")),
                        ),
                        "overall": stats.get("overall", "0-0"),
                        "streak": stats.get("streak", "-"),
                    }
                )
            result.append(
                {"id": conference_id, "name": MAJOR_CONFERENCES[conference_id], "rows": rows}
            )
        result.sort(key=lambda item: list(MAJOR_CONFERENCES).index(item["id"]))
        return result

    @staticmethod
    def _select_lead_game(games: list[dict[str, Any]]) -> dict[str, Any] | None:
        completed = [game for game in games if game["completed"]]
        if not completed:
            return None
        return min(
            completed,
            key=lambda item: min(
                item["away"]["rank"] or 999,
                item["home"]["rank"] or 999,
            ),
        )

    @staticmethod
    def _story_for_game(game: dict[str, Any]) -> dict[str, Any]:
        winner = game["away"] if game["away"]["winner"] else game["home"]
        loser = game["home"] if winner is game["away"] else game["away"]
        rank = f"No. {winner['rank']} " if winner["rank"] else ""
        return {
            "headline": (
                f"{rank}{winner['name']} Tops {loser['name']}, "
                f"{winner['score']}-{loser['score']}"
            ),
            "deck": (
                f"The {winner['name']} supplied the defining result on the "
                "major-conference college football slate."
            ),
            "paragraphs": [
                (
                    f"{winner['name']} finished ahead of {loser['name']}, "
                    f"{winner['score']}-{loser['score']}, at {game['venue']}."
                ),
                "The result headlines a week spanning the ACC, Big Ten, Big 12, SEC and Pac-12.",
                (
                    "The Daily Sports Page keeps the national schedule, polls and "
                    "conference races together as the season develops."
                ),
            ],
            "ai_generated": False,
            "espn_game_id": game["id"],
            "edition_date": game["date"],
        }

    @classmethod
    def _lead_story(cls, games: list[dict[str, Any]]) -> dict[str, Any] | None:
        game = cls._select_lead_game(games)
        return cls._story_for_game(game) if game else None

    @staticmethod
    def _select_news_lead(payload: dict[str, Any]) -> dict[str, str] | None:
        return next(iter(NCAAFEditionGenerator._news_candidates(payload)), None)

    @staticmethod
    def _news_candidates(payload: dict[str, Any]) -> list[dict[str, str]]:
        candidates = []
        for article in payload.get("articles") or []:
            article_id = str(article.get("id") or "")
            headline = str(article.get("headline") or "").strip()
            description = str(article.get("description") or "").strip()
            api_url = str(
                ((article.get("links") or {}).get("api", {}).get("self") or {}).get(
                    "href", ""
                )
            )
            article_type = str(article.get("type") or "").casefold()
            if (
                article_id
                and headline
                and article.get("premium") is not True
                and "premium" not in article_type
                and "media" not in article_type
                and "content.core.api.espn.com" in api_url
            ):
                candidates.append({
                    "id": article_id,
                    "headline": headline,
                    "description": description,
                    "api_url": api_url,
                })
        return candidates

    async def generate(self, output_dir: Path) -> Path:
        return render_ncaaf_page(await self.collect(), output_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", type=date.fromisoformat, default=date.today() - timedelta(days=1))
    parser.add_argument("--build-dir", type=Path, default=Path("build/ncaaf"))
    args = parser.parse_args()
    path = asyncio.run(NCAAFEditionGenerator(args.date).generate(args.build_dir))
    print(f"NCAAF edition rendered to {path}")


if __name__ == "__main__":
    main()

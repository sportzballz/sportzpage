# src/collectors/mlb.py
from __future__ import annotations
import asyncio
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional
from src.collectors.base import Collector, ProviderUnavailableError
from src.storage.cache import ResponseCache

logger = logging.getLogger(__name__)

# Default freshness max ages (seconds)
DEFAULT_MAX_AGE = {
    "schedule": 300,
    "standings": 1800,
    "transactions": 1800,
    "injuries": 7200,
    "stats_leaders": 21600,
    "teams": 86400,
    "boxscore": 86400,
}

# Batting categories to collect
BATTING_CATEGORIES = [
    "battingAverage",
    "onBasePercentage",
    "sluggingPercentage",
    "onBasePlusSlugging",
    "homeRuns",
    "runsBattedIn",
    "runs",
    "hits",
    "doubles",
    "triples",
    "stolenBases",
    "baseOnBalls",
    "strikeOuts",
    "totalBases",
]

# Pitching categories to collect
PITCHING_CATEGORIES = [
    "earnedRunAverage",
    "wins",
    "strikeOuts",
    "walksAndHitsPerInningPitched",
    "saves",
    "inningsPitched",
    "qualityStarts",
    "completeGames",
    "shutouts",
    "opponentsBattingAverage",
    "strikeoutsPer9Inn",
    "baseOnBallsPer9",
    "homeRunsPer9",
]


class MLBCollector(Collector):
    """Collector for the MLB Stats API."""

    def __init__(
        self,
        game_date: date,
        cache: Optional[ResponseCache] = None,
        max_age_overrides: Optional[dict] = None,
        fixture_output_dir: Optional[Path] = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(base_url="https://statsapi.mlb.com/api/v1", **kwargs)
        self._game_date = game_date
        self._cache = cache
        self._max_ages = {**DEFAULT_MAX_AGE, **(max_age_overrides or {})}
        self._fixture_output_dir = fixture_output_dir

    async def get_teams(self) -> dict[int, str]:
        """Fetch all MLB teams and return a map of team_id -> abbreviation."""
        key = "teams_abbr_map"
        if self._cache:
            cached = self._cache.get(key, self._max_ages["teams"])
            if cached is not None:
                return {int(k): v for k, v in cached.items()}
        data = await self._get("/teams", params={"sportId": 1, "activeStatus": "Active"})
        abbr_map = {
            t["id"]: t.get("abbreviation", t.get("teamCode", "UNK")) for t in data.get("teams", [])
        }
        if self._cache:
            self._cache.set(key, {str(k): v for k, v in abbr_map.items()})
        self._maybe_save_fixture("teams", data)
        return abbr_map

    async def get_schedule(self, target_date: Optional[date] = None) -> Any:
        """Fetch full schedule for the target date including linescore.

        If the target date returns no games, automatically falls back to yesterday.
        """
        fetch_date = target_date or self._game_date
        key = f"schedule_{fetch_date}"
        if self._cache:
            cached = self._cache.get(key, self._max_ages["schedule"])
            if cached is not None:
                return cached
        data = await self._get(
            "/schedule",
            params={
                "sportId": 1,
                "date": fetch_date.strftime("%m/%d/%Y"),
                "hydrate": "linescore,probablePitcher(note),broadcasts(all),decisions,weather",
            },
        )
        # Fall back to yesterday if today has no games yet
        if data.get("totalGames", 0) == 0 and fetch_date == self._game_date:
            yesterday = fetch_date - timedelta(days=1)
            logger.info("no games found for %s, falling back to %s", fetch_date, yesterday)
            return await self.get_schedule(target_date=yesterday)
        if self._cache:
            self._cache.set(key, data)
        self._maybe_save_fixture("schedule", data)
        return data

    async def get_standings(self) -> Any:
        """Fetch current standings for all divisions."""
        key = f"standings_{self._game_date}"
        if self._cache:
            cached = self._cache.get(key, self._max_ages["standings"])
            if cached is not None:
                return cached
        data = await self._get(
            "/standings",
            params={"leagueId": "103,104", "standingsType": "regularSeason"},
        )
        if self._cache:
            self._cache.set(key, data)
        self._maybe_save_fixture("standings", data)
        return data

    async def get_stats_leaders(self, stat_group: str, stat_type: str, season: int) -> Any:
        """Fetch league leaders for a single stat category."""
        key = f"leaders_{stat_group}_{stat_type}_{season}"
        if self._cache:
            cached = self._cache.get(key, self._max_ages["stats_leaders"])
            if cached is not None:
                return cached
        data = await self._get(
            "/stats/leaders",
            params={
                "leaderCategories": stat_type,
                "statGroup": stat_group,
                "season": season,
                "limit": 10,
                "sportId": 1,
            },
        )
        if self._cache:
            self._cache.set(key, data)
        self._maybe_save_fixture(f"leaders_{stat_group}_{stat_type}", data)
        return data

    async def get_all_leaders(self, season: int) -> dict[str, Any]:
        """Fetch all batting and pitching leader categories concurrently."""
        key = f"all_leaders_{season}"
        if self._cache:
            cached = self._cache.get(key, self._max_ages["stats_leaders"])
            if cached is not None:
                return cached

        async def _fetch(stat_group: str, category: str) -> tuple[str, Any]:
            try:
                data = await self.get_stats_leaders(stat_group, category, season)
                return (category, data)
            except Exception as exc:
                logger.warning("leaders %s/%s unavailable: %s", stat_group, category, exc)
                return (category, None)

        batting_tasks = [_fetch("hitting", cat) for cat in BATTING_CATEGORIES]
        pitching_tasks = [_fetch("pitching", cat) for cat in PITCHING_CATEGORIES]
        results = await asyncio.gather(*batting_tasks, *pitching_tasks)

        leaders: dict[str, Any] = {}
        for category, data in results:
            if data is not None:
                leaders[category] = data

        if self._cache:
            self._cache.set(key, leaders)
        return leaders

    async def get_team_player_stats(self, season: int) -> dict[str, Any]:
        """Fetch season stats for every MLB player so club leaders can be calculated."""
        key = f"team_player_stats_{season}"
        if self._cache:
            cached = self._cache.get(key, self._max_ages["stats_leaders"])
            if cached is not None:
                return cached

        async def fetch(group: str) -> Any:
            return await self._get(
                "/stats",
                params={
                    "stats": "season",
                    "group": group,
                    "season": season,
                    "sportIds": 1,
                    "playerPool": "ALL",
                    "hydrate": "team",
                    "limit": 2000,
                },
            )

        hitting, pitching = await asyncio.gather(fetch("hitting"), fetch("pitching"))
        data = {"hitting": hitting, "pitching": pitching}
        if self._cache:
            self._cache.set(key, data)
        self._maybe_save_fixture("team_player_stats", data)
        return data

    async def get_transactions(self) -> Any:
        """Fetch recent transactions."""
        key = f"transactions_{self._game_date}"
        if self._cache:
            cached = self._cache.get(key, self._max_ages["transactions"])
            if cached is not None:
                return cached
        date_str = self._game_date.strftime("%Y-%m-%d")
        data = await self._get("/transactions", params={"date": date_str, "sportId": 1})
        if self._cache:
            self._cache.set(key, data)
        self._maybe_save_fixture("transactions", data)
        return data

    async def get_injuries(self) -> Any:
        """Fetch current injury report."""
        key = f"injuries_{self._game_date}"
        if self._cache:
            cached = self._cache.get(key, self._max_ages["injuries"])
            if cached is not None:
                return cached
        data = await self._get("/injuries", params={"sportId": 1})
        if self._cache:
            self._cache.set(key, data)
        self._maybe_save_fixture("injuries", data)
        return data

    async def get_boxscore(self, game_id: int) -> dict[str, Any]:
        """Fetch the full player-level box score for one game."""
        key = f"boxscore_{game_id}"
        if self._cache:
            cached = self._cache.get(key, self._max_ages["boxscore"])
            if cached is not None:
                return cached
        data = await self._get(f"/game/{game_id}/boxscore")
        if self._cache:
            self._cache.set(key, data)
        return data

    async def get_boxscores(self, schedule: dict[str, Any]) -> dict[str, Any]:
        """Fetch full box scores for completed games, tolerating individual failures."""
        game_ids = [
            game["gamePk"]
            for date_entry in schedule.get("dates", [])
            for game in date_entry.get("games", [])
            if game.get("status", {}).get("detailedState") in {"Final", "Game Over"}
        ]

        async def fetch(game_id: int) -> tuple[str, dict[str, Any] | None]:
            try:
                return str(game_id), await self.get_boxscore(game_id)
            except Exception as exc:
                logger.warning("box score unavailable for game %d: %s", game_id, exc)
                return str(game_id), None

        results = await asyncio.gather(*(fetch(game_id) for game_id in game_ids))
        return {game_id: data for game_id, data in results if data is not None}

    async def collect(self) -> dict[str, Any]:
        """Collect all data needed for an edition. Returns raw responses keyed by domain.

        Schedule, standings, and leaders are fetched concurrently.
        Transactions and injuries are optional — failure logs a warning and continues.
        If today has no games, schedule automatically falls back to yesterday.
        """
        season = self._game_date.year

        # Required: fetch concurrently
        schedule, standings, leaders, teams, team_player_stats = await asyncio.gather(
            self.get_schedule(),
            self.get_standings(),
            self.get_all_leaders(season),
            self.get_teams(),
            self.get_team_player_stats(season),
        )
        boxscores = await self.get_boxscores(schedule)

        # Optional: transactions
        try:
            transactions = await self.get_transactions()
        except (ProviderUnavailableError, Exception) as exc:
            logger.warning("transactions unavailable, continuing without: %s", exc)
            transactions = {"transactions": []}

        # Optional: injuries
        try:
            injuries = await self.get_injuries()
        except (ProviderUnavailableError, Exception) as exc:
            logger.warning("injuries unavailable, continuing without: %s", exc)
            injuries = {"injuries": []}

        return {
            "schedule": schedule,
            "standings": standings,
            "leaders": leaders,
            "team_player_stats": team_player_stats,
            "teams": teams,  # id -> abbreviation map
            "transactions": transactions,
            "injuries": injuries,
            "boxscores": boxscores,
        }

    def _maybe_save_fixture(self, name: str, data: Any) -> None:
        """Save raw response as a test fixture if fixture_output_dir is set."""
        if not self._fixture_output_dir:
            return
        import json

        self._fixture_output_dir.mkdir(parents=True, exist_ok=True)
        path = self._fixture_output_dir / f"{name}.json"
        path.write_text(json.dumps(data, indent=2))
        logger.debug("saved fixture: %s", path)

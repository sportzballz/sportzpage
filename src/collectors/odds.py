from __future__ import annotations

import logging
from datetime import date
from typing import Any

import httpx

logger = logging.getLogger(__name__)

ESPN_SCOREBOARD_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
)
ESPN_TO_MLB_ABBR = {"ARI": "AZ", "CHW": "CWS"}


def _american(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


class OddsCollector:
    """Collect keyless pregame MLB moneylines and totals from ESPN."""

    def __init__(self, game_date: date, timeout: float = 15.0) -> None:
        self._game_date = game_date
        self._timeout = timeout

    @property
    def source_url(self) -> str:
        return f"{ESPN_SCOREBOARD_URL}?dates={self._game_date:%Y%m%d}&limit=100"

    async def collect(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(self.source_url, follow_redirects=True)
                response.raise_for_status()
                payload = response.json()
                items = self.parse(payload)
                covered = {(item["away_abbr"], item["home_abbr"]) for item in items}
                for event in payload.get("events", []):
                    competition = (event.get("competitions") or [{}])[0]
                    matchup = self._matchup(competition)
                    if not event.get("id") or not matchup or matchup in covered:
                        continue
                    try:
                        summary = await client.get(
                            "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary",
                            params={"event": event["id"]},
                            follow_redirects=True,
                        )
                        summary.raise_for_status()
                        item = self.parse_pickcenter(summary.json(), competition)
                        if item:
                            items.append(item)
                            covered.add(matchup)
                    except (httpx.HTTPError, ValueError) as exc:
                        logger.debug("ESPN summary odds unavailable for %s: %s", event["id"], exc)
            return {"source": "ESPN", "items": items, "events": self.parse_events(payload)}
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ESPN betting lines unavailable for %s: %s", self._game_date, exc)
            return {"source": "ESPN", "items": [], "events": [], "error": str(exc)}

    @classmethod
    def parse_events(cls, payload: dict[str, Any]) -> list[dict[str, str]]:
        events: list[dict[str, str]] = []
        for event in payload.get("events", []):
            competition = (event.get("competitions") or [{}])[0]
            matchup = cls._matchup(competition)
            if event.get("id") and matchup:
                events.append(
                    {
                        "espn_game_id": str(event["id"]),
                        "away_abbr": matchup[0],
                        "home_abbr": matchup[1],
                    }
                )
        return events

    @staticmethod
    def _matchup(competition: dict[str, Any]) -> tuple[str, str] | None:
        competitors = competition.get("competitors") or []
        home_team = next(
            (row.get("team", {}) for row in competitors if row.get("homeAway") == "home"),
            {},
        )
        away_team = next(
            (row.get("team", {}) for row in competitors if row.get("homeAway") == "away"),
            {},
        )
        home_abbr = ESPN_TO_MLB_ABBR.get(
            home_team.get("abbreviation"), home_team.get("abbreviation")
        )
        away_abbr = ESPN_TO_MLB_ABBR.get(
            away_team.get("abbreviation"), away_team.get("abbreviation")
        )
        return (away_abbr, home_abbr) if away_abbr and home_abbr else None

    @classmethod
    def parse(cls, payload: dict[str, Any]) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for event in payload.get("events", []):
            competition = (event.get("competitions") or [{}])[0]
            offers = competition.get("odds") or []
            if not offers:
                continue
            offer = offers[0]
            moneyline = offer.get("moneyline") or {}
            home = moneyline.get("home") or {}
            away = moneyline.get("away") or {}
            matchup = cls._matchup(competition)
            if not matchup:
                continue
            away_abbr, home_abbr = matchup
            home_ml = _american((home.get("close") or {}).get("odds"))
            away_ml = _american((away.get("close") or {}).get("odds"))
            try:
                run_total = float(offer["overUnder"]) if offer.get("overUnder") is not None else None
            except (TypeError, ValueError):
                run_total = None
            if not home_abbr or not away_abbr or not any(
                value is not None for value in (home_ml, away_ml, run_total)
            ):
                continue
            items.append(
                {
                    "away_abbr": away_abbr,
                    "home_abbr": home_abbr,
                    "away_moneyline": away_ml,
                    "home_moneyline": home_ml,
                    "run_total": run_total,
                    "provider": (offer.get("provider") or {}).get("displayName", "ESPN"),
                }
            )
        return items

    @classmethod
    def parse_pickcenter(
        cls, payload: dict[str, Any], competition: dict[str, Any]
    ) -> dict[str, Any] | None:
        offers = payload.get("pickcenter") or []
        matchup = cls._matchup(competition)
        if not offers or not matchup:
            return None
        offer = offers[0]
        away_abbr, home_abbr = matchup
        away_ml = _american((offer.get("awayTeamOdds") or {}).get("moneyLine"))
        home_ml = _american((offer.get("homeTeamOdds") or {}).get("moneyLine"))
        try:
            run_total = float(offer["overUnder"]) if offer.get("overUnder") is not None else None
        except (TypeError, ValueError):
            run_total = None
        if not any(value is not None for value in (away_ml, home_ml, run_total)):
            return None
        provider = offer.get("provider") or {}
        return {
            "away_abbr": away_abbr,
            "home_abbr": home_abbr,
            "away_moneyline": away_ml,
            "home_moneyline": home_ml,
            "run_total": run_total,
            "provider": provider.get("displayName") or provider.get("name") or "ESPN",
        }

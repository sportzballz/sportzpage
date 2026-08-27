# src/normalization/normalizer.py
from __future__ import annotations
import logging
from datetime import date, datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field
from src.models.game import BettingLine, Game, GameStatus, LinescoreInning, Pitcher, TeamBoxLine, TeamGameLine
from src.models.history import HistoricalItem
from src.history_text import split_sentences
from src.models.standings import (
    DivisionStandings,
    PlayoffStandings,
    Standings,
    StandingsRow,
    WildCardStandings,
)
from src.models.leaders import LeaderEntry, LeagueLeaders, TeamSeasonLeaders, TeamStatLeader
from src.models.transactions import Transaction, TransactionType
from src.models.story import Story, StoryType
from src.models.injuries import Injury, RosterStatus, InjuryConfidence

logger = logging.getLogger(__name__)

MLB_DIVISION_NAMES = {
    201: "AL East",
    202: "AL Central",
    200: "AL West",
    204: "NL East",
    205: "NL Central",
    203: "NL West",
}


class NormalizedData(BaseModel):
    """All provider data normalized to domain models, ready for editorial processing."""

    games: List[Game] = Field(default_factory=list)
    standings: Optional[Standings] = Field(default=None)
    league_leaders: Optional[LeagueLeaders] = Field(default=None)
    team_season_leaders: List[TeamSeasonLeaders] = Field(default_factory=list)
    transactions: List[Transaction] = Field(default_factory=list)
    injuries: List[Injury] = Field(default_factory=list)
    historical_items: List[HistoricalItem] = Field(default_factory=list)
    news_stories: List[Story] = Field(default_factory=list)
    collection_errors: List[str] = Field(default_factory=list)


class Normalizer:
    """Converts raw MLB Stats API responses to validated Pydantic domain models."""

    _GAME_STATUS_MAP: dict[str, GameStatus] = {
        "Final": GameStatus.final,
        "Game Over": GameStatus.final,
        "In Progress": GameStatus.in_progress,
        "Scheduled": GameStatus.scheduled,
        "Pre-Game": GameStatus.scheduled,
        "Warmup": GameStatus.scheduled,
        "Postponed": GameStatus.postponed,
        "Delayed": GameStatus.delayed,
        "Delayed: Rain": GameStatus.delayed,
        "Suspended": GameStatus.suspended,
    }

    _TRANSACTION_TYPE_MAP: dict[str, TransactionType] = {
        "Trade": TransactionType.trade,
        "Designated for Assignment": TransactionType.dfa,
        "Released": TransactionType.released,
        "Signed": TransactionType.signed,
        "Optioned to Minors": TransactionType.optioned,
        "Recalled from Minors": TransactionType.recalled,
        "Placed on 10-Day IL": TransactionType.injury,
        "Placed on 15-Day IL": TransactionType.injury,
        "Placed on 60-Day IL": TransactionType.injury,
        "Activated from IL": TransactionType.activated,
        "Claimed off Waivers": TransactionType.claimed,
        "Retired": TransactionType.retired,
    }

    def normalize(self, raw: dict[str, Any]) -> NormalizedData:
        # Build team abbreviation map: id (int) -> abbr string
        # Prefer the dedicated teams map; fall back to scanning schedule games
        teams_map: dict[int, str] = {}
        if "teams" in raw and isinstance(raw["teams"], dict):
            teams_map = {int(k): v for k, v in raw["teams"].items()}

        result = NormalizedData()
        if "schedule" in raw:
            result.games = self._normalize_schedule(
                raw["schedule"], teams_map, raw.get("boxscores", {}), raw.get("odds", {})
            )
        if "standings" in raw:
            result.standings = self._normalize_standings(raw["standings"], teams_map)
        if "transactions" in raw:
            result.transactions = self._normalize_transactions(raw["transactions"], teams_map)
        if "injuries" in raw:
            result.injuries = self._normalize_injuries(raw["injuries"])
        if "leaders" in raw:
            result.league_leaders = self._normalize_leaders(raw["leaders"])
        if "team_player_stats" in raw:
            result.team_season_leaders = self._normalize_team_leaders(raw["team_player_stats"])
        if "history" in raw:
            result.historical_items = self._normalize_history(raw["history"])
        if "news" in raw:
            result.news_stories = self._normalize_news(raw["news"])
        return result

    def _normalize_news(self, raw: dict[str, Any]) -> list[Story]:
        source = raw.get("source", "MLB.com")
        stories = []
        for item in raw.get("items", []):
            title = " ".join(str(item.get("title", "")).split())
            summary = " ".join(str(item.get("summary", "")).split())
            url = str(item.get("link", "")).strip()
            if not title or not summary or not url:
                continue
            stories.append(
                Story(
                    headline=title,
                    deck=summary,
                    byline=item.get("author") or source,
                    paragraphs=[summary],
                    source_data_references=[url],
                    story_type=StoryType.editorial,
                    facts_used=[summary],
                    ai_generated=False,
                    source_name=source,
                    source_url=url,
                )
            )
        return stories

    def _normalize_team_leaders(self, raw: dict[str, Any]) -> list[TeamSeasonLeaders]:
        """Calculate category leaders within each club from all-player season stats."""
        teams: dict[int, dict[str, Any]] = {}
        for group in ("hitting", "pitching"):
            payload = raw.get(group, {})
            stats_blocks = payload.get("stats", []) if isinstance(payload, dict) else []
            splits = stats_blocks[0].get("splits", []) if stats_blocks else []
            for split in splits:
                team = split.get("team", {})
                person = split.get("player") or split.get("person") or {}
                team_id = team.get("id")
                if not team_id or not person.get("fullName"):
                    continue
                bucket = teams.setdefault(
                    int(team_id),
                    {
                        "abbr": team.get("abbreviation", ""),
                        "name": team.get("name", ""),
                        "hitting": [],
                        "pitching": [],
                    },
                )
                bucket[group].append(
                    {
                        "player_id": int(person.get("id", 0)),
                        "player_name": person["fullName"],
                        "stat": split.get("stat", {}),
                    }
                )

        batting_categories = (
            ("avg", "AVG", False),
            ("homeRuns", "HR", False),
            ("rbi", "RBI", False),
            ("ops", "OPS", False),
            ("stolenBases", "SB", False),
        )
        pitching_categories = (
            ("era", "ERA", True),
            ("wins", "W", False),
            ("strikeOuts", "SO", False),
            ("saves", "SV", False),
            ("whip", "WHIP", True),
        )

        def pick(players: list[dict[str, Any]], categories):
            result: list[TeamStatLeader] = []
            for key, label, lower_is_better in categories:
                eligible = players
                if key in {"avg", "ops"}:
                    eligible = [p for p in players if int(p["stat"].get("plateAppearances", 0)) >= 100]
                elif key in {"era", "whip"}:
                    eligible = [p for p in players if float(p["stat"].get("inningsPitched", 0) or 0) >= 20]
                values = []
                for player in eligible:
                    value = player["stat"].get(key)
                    try:
                        values.append((float(value), player, str(value)))
                    except (TypeError, ValueError):
                        continue
                if not values:
                    continue
                _, player, value = (
                    min(values, key=lambda item: item[0])
                    if lower_is_better
                    else max(values, key=lambda item: item[0])
                )
                result.append(
                    TeamStatLeader(
                        category=key,
                        label=label,
                        player_id=player["player_id"],
                        player_name=player["player_name"],
                        value=value,
                    )
                )
            return result

        result = []
        for team_id, data in teams.items():
            batting = pick(data["hitting"], batting_categories)
            pitching = pick(data["pitching"], pitching_categories)
            if batting or pitching:
                result.append(
                    TeamSeasonLeaders(
                        team_id=team_id,
                        team_abbr=data["abbr"],
                        team_name=data["name"],
                        batting=batting,
                        pitching=pitching,
                    )
                )
        return sorted(result, key=lambda team: (team.team_abbr != "PHI", team.team_name))

    def _normalize_history(self, raw: dict[str, Any]) -> list[HistoricalItem]:
        source = raw.get("source", "")
        result: list[HistoricalItem] = []
        for event in raw.get("items", []):
            try:
                description = " ".join(str(event["description"]).split())
                sentences = split_sentences(description)
                full_event = sentences[0].rstrip(".!?") if sentences else description
                if len(full_event) > 110:
                    split_at = full_event.rfind(" ", 0, 111)
                    split_at = split_at if split_at > 60 else 110
                    headline = full_event[:split_at].rstrip()
                    detail = full_event[split_at:].lstrip(" ,;:–—-")
                else:
                    headline = full_event
                    detail = ""
                result.append(
                    HistoricalItem(
                        year=int(event["year"]),
                        headline=headline,
                        description=detail,
                        source=source,
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                logger.warning("failed to normalize historical event: %s", exc)
        return result

    def _normalize_schedule(
        self,
        raw: dict[str, Any],
        teams_map: dict[int, str] = {},
        boxscores: dict[str, Any] = {},
        odds: dict[str, Any] = {},
    ) -> list[Game]:
        odds_by_matchup: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for item in odds.get("items", []):
            key = (str(item.get("away_abbr", "")), str(item.get("home_abbr", "")))
            odds_by_matchup.setdefault(key, []).append(item)
        espn_ids_by_matchup: dict[tuple[str, str], list[str]] = {}
        for event in odds.get("events", []):
            key = (str(event.get("away_abbr", "")), str(event.get("home_abbr", "")))
            if event.get("espn_game_id"):
                espn_ids_by_matchup.setdefault(key, []).append(str(event["espn_game_id"]))
        games: list[Game] = []
        for date_entry in raw.get("dates", []):
            for g in date_entry.get("games", []):
                try:
                    game = self._parse_game(g, teams_map, date_entry.get("date"))
                    boxscore = boxscores.get(str(game.game_id))
                    if boxscore:
                        game = self._add_boxscore(game, boxscore)
                    matchup = (game.away.team_abbr, game.home.team_abbr)
                    espn_ids = espn_ids_by_matchup.get(matchup, [])
                    if espn_ids:
                        game = game.model_copy(update={"espn_game_id": espn_ids.pop(0)})
                    offers = odds_by_matchup.get(matchup, [])
                    if offers:
                        offer = offers.pop(0)
                        game = game.model_copy(
                            update={
                                "betting_line": BettingLine(
                                    away_moneyline=offer.get("away_moneyline"),
                                    home_moneyline=offer.get("home_moneyline"),
                                    run_total=offer.get("run_total"),
                                    provider=offer.get("provider") or odds.get("source", "ESPN"),
                                )
                            }
                        )
                    games.append(game)
                except Exception as exc:
                    logger.warning("failed to parse game %s: %s", g.get("gamePk"), exc)
        return games

    def _add_boxscore(self, game: Game, raw: dict[str, Any]) -> Game:
        batting: dict[str, list[TeamBoxLine]] = {}
        pitching: dict[str, list[TeamBoxLine]] = {}
        notes: list[str] = []

        for side in ("away", "home"):
            team = raw.get("teams", {}).get(side, {})
            abbr = game.away.team_abbr if side == "away" else game.home.team_abbr
            players = team.get("players", {})
            batting[abbr] = [
                self._parse_batter(players.get(f"ID{player_id}", {}))
                for player_id in team.get("batters", [])
                if players.get(f"ID{player_id}", {}).get("stats", {}).get("batting")
            ]
            pitching[abbr] = [
                self._parse_box_pitcher(players.get(f"ID{player_id}", {}))
                for player_id in team.get("pitchers", [])
                if players.get(f"ID{player_id}", {}).get("stats", {}).get("pitching")
            ]
        game_info = {item.get("label"): item.get("value") for item in raw.get("info", [])}
        for label in ("HBP", "Umpires"):
            if game_info.get(label):
                notes.append(f"{label}: {game_info[label]}")

        attendance_text = str(game_info.get("Att", "")).replace(",", "").rstrip(".")
        attendance = int(attendance_text) if attendance_text.isdigit() else None
        duration = str(game_info.get("T", "")).rstrip(".") or None
        return game.model_copy(
            update={
                "batting_lines": batting,
                "pitching_lines": pitching,
                "boxscore_notes": notes,
                "attendance": attendance,
                "time_of_game": duration,
            }
        )

    def _parse_batter(self, player: dict[str, Any]) -> TeamBoxLine:
        stats = player.get("stats", {}).get("batting", {})
        season = player.get("seasonStats", {}).get("batting", {})
        person = player.get("person", {})
        return TeamBoxLine(
            player_name=person.get("boxscoreName", person.get("fullName", "Unknown")),
            player_id=person.get("id", 0),
            position=player.get("position", {}).get("abbreviation"),
            ab=stats.get("atBats"),
            r=stats.get("runs"),
            h=stats.get("hits"),
            rbi=stats.get("rbi"),
            bb=stats.get("baseOnBalls"),
            k=stats.get("strikeOuts"),
            avg=season.get("avg"),
        )

    def _parse_box_pitcher(self, player: dict[str, Any]) -> TeamBoxLine:
        stats = player.get("stats", {}).get("pitching", {})
        season = player.get("seasonStats", {}).get("pitching", {})
        person = player.get("person", {})
        note = stats.get("note", "")
        decision = next(
            (code for code in ("W", "L", "S", "H", "BS") if f"({code}," in note),
            None,
        )
        return TeamBoxLine(
            player_name=person.get("boxscoreName", person.get("fullName", "Unknown")),
            player_id=person.get("id", 0),
            ip=stats.get("inningsPitched"),
            hits_allowed=stats.get("hits"),
            r=stats.get("runs"),
            er=stats.get("earnedRuns"),
            bb_allowed=stats.get("baseOnBalls"),
            k_pitched=stats.get("strikeOuts"),
            pitches=stats.get("numberOfPitches"),
            era=season.get("era"),
            decision=decision,
        )

    def _parse_game(
        self,
        g: dict[str, Any],
        teams_map: dict[int, str] = {},
        schedule_date: str | None = None,
    ) -> Game:
        status_detail = g.get("status", {}).get("detailedState", "Scheduled")
        status = self._GAME_STATUS_MAP.get(status_detail, GameStatus.scheduled)
        teams = g.get("teams", {})
        linescore = g.get("linescore", {})
        innings_raw = linescore.get("innings", [])
        innings = [
            LinescoreInning(
                inning=inn.get("num", i + 1),
                away_runs=inn.get("away", {}).get("runs"),
                home_runs=inn.get("home", {}).get("runs"),
            )
            for i, inn in enumerate(innings_raw)
        ]
        decisions = g.get("decisions", {})
        broadcasts = [b.get("name", "") for b in g.get("broadcasts", []) if b.get("name")]

        return Game(
            game_id=g["gamePk"],
            # MLB's gameDate is UTC and rolls evening West Coast games into the
            # following date. The enclosing schedule date is the local baseball date.
            game_date=schedule_date or g.get("gameDate", "")[:10],
            game_time_et=self._format_time(g.get("gameDate", "")),
            status=status,
            inning=linescore.get("currentInning"),
            inning_state=linescore.get("inningState"),
            home=self._parse_team_line(
                teams.get("home", {}), linescore.get("teams", {}).get("home", {}), teams_map
            ),
            away=self._parse_team_line(
                teams.get("away", {}), linescore.get("teams", {}).get("away", {}), teams_map
            ),
            linescore=innings,
            home_probable_pitcher=self._parse_pitcher(teams.get("home", {}).get("probablePitcher")),
            away_probable_pitcher=self._parse_pitcher(teams.get("away", {}).get("probablePitcher")),
            winning_pitcher=self._parse_pitcher(decisions.get("winner")),
            losing_pitcher=self._parse_pitcher(decisions.get("loser")),
            save_pitcher=self._parse_pitcher(decisions.get("save")),
            venue_name=g.get("venue", {}).get("name"),
            venue_city=g.get("venue", {}).get("location", {}).get("city"),
            tv_broadcasts=broadcasts,
            weather_description=g.get("weather", {}).get("condition"),
            is_doubleheader=g.get("doubleHeader", "N") != "N",
            doubleheader_game_num=g.get("gameNumber"),
            recap_anchor=f"recap-{g['gamePk']}",
        )

    def _parse_team_line(self, team: dict, line: dict, teams_map: dict = {}) -> TeamGameLine:
        team_id = team.get("team", {}).get("id", 0)
        # Prefer abbreviation from the teams_map (fetched from /teams endpoint)
        # since schedule response doesn't include abbreviation
        abbr = teams_map.get(team_id) or team.get("team", {}).get("abbreviation", "")
        return TeamGameLine(
            team_id=team_id,
            team_abbr=abbr or "UNK",
            team_name=team.get("team", {}).get("name", "Unknown"),
            runs=line.get("runs"),
            hits=line.get("hits"),
            errors=line.get("errors"),
        )

    def _parse_pitcher(self, data: dict | None) -> Pitcher | None:
        if not data:
            return None
        stats = data.get("stats", [{}])[0].get("stats", {}) if data.get("stats") else {}
        return Pitcher(
            player_id=data.get("id", 0),
            name=data.get("fullName", data.get("name", "")),
            handedness=data.get("pitchHand", {}).get("code") if data.get("pitchHand") else None,
            wins=stats.get("wins"),
            losses=stats.get("losses"),
            era=float(stats["era"]) if stats.get("era") else None,
        )

    def _format_time(self, iso: str) -> str | None:
        if not iso:
            return None
        try:
            import pytz

            dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
            et = dt.astimezone(pytz.timezone("America/New_York"))
            return et.strftime("%-I:%M %p ET")
        except Exception:
            return None

    def _normalize_standings(
        self, raw: dict[str, Any], teams_map: dict[int, str] = {}
    ) -> Standings:
        divisions: list[DivisionStandings] = []
        seen_division_ids: set[int] = set()

        for record in raw.get("records", []):
            div = record.get("division", {})
            div_id = div.get("id", 0)
            div_name = (
                div.get("nameShort") or div.get("name") or MLB_DIVISION_NAMES.get(div_id, "")
            )
            rows = [
                self._parse_standings_row(tr, teams_map) for tr in record.get("teamRecords", [])
            ]
            if rows and div_id not in seen_division_ids:
                divisions.append(
                    DivisionStandings(division_id=div_id, division_name=div_name, rows=rows)
                )
                seen_division_ids.add(div_id)

        playoff_pictures: list[PlayoffStandings] = []
        wild_cards: list[WildCardStandings] = []
        for league in ("AL", "NL"):
            league_rows = [
                row
                for division in divisions
                if division.division_name.startswith(league)
                for row in division.rows
            ]
            division_leaders = sorted(
                (row for row in league_rows if row.division_leader),
                key=lambda row: row.league_rank or 99,
            )
            wild_card_rows = sorted(
                (
                    row
                    for row in league_rows
                    if not row.division_leader and row.wild_card_rank is not None
                ),
                key=lambda row: row.wild_card_rank or 99,
            )
            if wild_card_rows:
                wild_cards.append(WildCardStandings(league=league, rows=wild_card_rows))

            playoff_rows = [
                row.model_copy(update={"playoff_seed": seed})
                for seed, row in enumerate(
                    [*division_leaders, *wild_card_rows[:3]], start=1
                )
            ]
            if playoff_rows:
                playoff_pictures.append(
                    PlayoffStandings(league=league, rows=playoff_rows)
                )

        return Standings(
            divisions=divisions,
            playoff_pictures=playoff_pictures,
            wild_cards=wild_cards,
        )

    def _parse_standings_row(
        self, tr: dict[str, Any], teams_map: dict[int, str] = {}
    ) -> StandingsRow:
        team = tr.get("team", {})
        team_id = team.get("id", 0)
        abbr = teams_map.get(team_id) or team.get("abbreviation", "")
        split_records = {r.get("type"): r for r in tr.get("records", {}).get("splitRecords", [])}
        home = split_records.get("home", {})
        away = split_records.get("away", {})
        last_10 = split_records.get("lastTen", {})
        streak = tr.get("streak", {}).get("streakCode", "")
        division_rank = self._optional_rank(tr.get("divisionRank"))
        return StandingsRow(
            team_id=team_id,
            team_abbr=abbr or "UNK",
            team_name=team.get("name", ""),
            wins=tr.get("wins", 0),
            losses=tr.get("losses", 0),
            pct=float(tr.get("winningPercentage", "0.000")),
            games_back=tr.get("gamesBack", "-"),
            last_10=f"{last_10.get('wins', 0)}-{last_10.get('losses', 0)}",
            streak=streak,
            home_record=f"{home.get('wins', 0)}-{home.get('losses', 0)}",
            away_record=f"{away.get('wins', 0)}-{away.get('losses', 0)}",
            run_differential=tr.get("runDifferential", 0),
            wild_card_gb=tr.get("wildCardGamesBack"),
            division_rank=division_rank,
            league_rank=self._optional_rank(tr.get("leagueRank")),
            wild_card_rank=self._optional_rank(tr.get("wildCardRank")),
            division_leader=division_rank == 1,
        )

    @staticmethod
    def _optional_rank(value: Any) -> int | None:
        try:
            return int(value) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    def _normalize_transactions(
        self, raw: dict[str, Any], teams_map: dict[int, str] | None = None
    ) -> list[Transaction]:
        teams_map = teams_map or {}
        seen: set[str] = set()
        result: list[Transaction] = []
        for t in raw.get("transactions", []):
            tid = str(t.get("id", ""))
            if tid in seen:
                continue
            seen.add(tid)
            try:
                team = t.get("fromTeam") or t.get("toTeam") or {}
                result.append(
                    Transaction(
                        transaction_id=tid,
                        team_abbr=team.get("abbreviation", teams_map.get(team.get("id"), "")),
                        team_name=team.get("name", ""),
                        player_name=t.get("person", {}).get("fullName", ""),
                        player_id=t.get("person", {}).get("id"),
                        transaction_type=self._classify_transaction(t),
                        effective_date=date.fromisoformat(t["date"][:10]),
                        explanation=t.get("description", t.get("typeDesc", "")),
                        source_timestamp=datetime.fromisoformat(
                            t.get("date", "2026-01-01T00:00:00").replace("Z", "+00:00")
                        ),
                    )
                )
            except Exception as exc:
                logger.warning("skipping transaction %s: %s", tid, exc)
        return result

    def _classify_transaction(self, transaction: dict[str, Any]) -> TransactionType:
        """Classify injury-list activity independently from generic status changes."""
        type_desc = str(transaction.get("typeDesc", ""))
        description = str(transaction.get("description", ""))
        description_lower = description.lower()

        if "injured list" in description_lower or "rehab assignment" in description_lower:
            if "activated" in description_lower:
                return TransactionType.activated
            return TransactionType.injury

        return self._TRANSACTION_TYPE_MAP.get(type_desc, TransactionType.other)

    def _normalize_injuries(self, raw: dict[str, Any]) -> list[Injury]:
        result: list[Injury] = []
        for item in raw.get("injuries", []):
            try:
                result.append(
                    Injury(
                        player_id=item.get("player", {}).get("id", 0),
                        player_name=item.get("player", {}).get("fullName", ""),
                        team_abbr=item.get("team", {}).get("abbreviation", ""),
                        injury_description=item.get("notes", ""),
                        roster_status=RosterStatus.ten_day_il,
                        confidence_level=InjuryConfidence.reported,
                    )
                )
            except Exception as exc:
                logger.warning("skipping injury: %s", exc)
        return result

    # Mapping from MLB Stats API leaderCategory names to internal short keys
    _BATTING_CATEGORY_MAP: dict[str, str] = {
        "battingAverage": "avg",
        "onBasePercentage": "obp",
        "sluggingPercentage": "slg",
        "onBasePlusSlugging": "ops",
        "homeRuns": "hr",
        "runsBattedIn": "rbi",
        "runs": "r",
        "hits": "h",
        "doubles": "doubles",
        "triples": "triples",
        "stolenBases": "sb",
        "baseOnBalls": "bb",
        "strikeOuts": "so",
        "totalBases": "tb",
        "extraBaseHits": "xbh",
    }
    _PITCHING_CATEGORY_MAP: dict[str, str] = {
        "earnedRunAverage": "era",
        "wins": "wins",
        "strikeOuts": "k",
        "walksAndHitsPerInningPitched": "whip",
        "saves": "saves",
        "holds": "holds",
        "inningsPitched": "ip",
        "qualityStarts": "qs",
        "completeGames": "cg",
        "shutouts": "sho",
        "opponentsBattingAverage": "opp_avg",
        "strikeoutsPer9Inn": "k9",
        "baseOnBallsPer9": "bb9",
        "homeRunsPer9": "hr9",
    }

    def _normalize_leaders(self, raw: dict[str, Any]) -> LeagueLeaders:
        """Convert raw leaders dict (category -> API response) to LeagueLeaders model."""
        batting: dict[str, list[LeaderEntry]] = {}
        pitching: dict[str, list[LeaderEntry]] = {}

        for api_category, data in raw.items():
            if data is None:
                continue
            short_key = (
                self._BATTING_CATEGORY_MAP.get(api_category)
                or self._PITCHING_CATEGORY_MAP.get(api_category)
                or api_category
            )
            is_pitching = api_category in self._PITCHING_CATEGORY_MAP
            entries: list[LeaderEntry] = []
            for leader_block in data.get("leagueLeaders", []):
                for rank_idx, leader in enumerate(leader_block.get("leaders", []), start=1):
                    try:
                        person = leader.get("person", {})
                        team = leader.get("team", {})
                        entries.append(
                            LeaderEntry(
                                rank=leader.get("rank", rank_idx),
                                player_id=person.get("id", 0),
                                player_name=person.get("fullName", ""),
                                team_abbr=team.get(
                                    "abbreviation", team.get("name", "")[:3].upper()
                                ),
                                position=leader.get("position", {}).get(
                                    "abbreviation", "P" if is_pitching else ""
                                ),
                                value=str(leader.get("value", "")),
                                games_played=leader.get("season", 0),
                                league=leader.get("league", {}).get("abbreviation", "MLB"),
                                qualified=True,
                            )
                        )
                    except Exception as exc:
                        logger.warning("skipping leader entry in %s: %s", api_category, exc)
            if entries:
                if is_pitching:
                    pitching[short_key] = entries
                else:
                    batting[short_key] = entries

        return LeagueLeaders(batting=batting, pitching=pitching)

# tests/unit/test_normalization.py
from __future__ import annotations
import pytest
from src.models.game import GameStatus
from src.models.transactions import TransactionType
from src.normalization.normalizer import Normalizer, NormalizedData


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_team(team_id: int, abbr: str, name: str, runs: int | None = None) -> tuple[dict, dict]:
    team_info = {"id": team_id, "abbreviation": abbr, "name": name}
    linescore_line: dict = {}
    if runs is not None:
        linescore_line["runs"] = runs
    return {"team": team_info}, linescore_line


def _make_game(
    game_pk: int,
    status: str,
    home_runs: int | None = None,
    away_runs: int | None = None,
    double_header: str = "N",
    game_number: int = 1,
    decisions: dict | None = None,
) -> dict:
    home_team_info, home_line = _make_team(1, "NYY", "New York Yankees", home_runs)
    away_team_info, away_line = _make_team(2, "BOS", "Boston Red Sox", away_runs)
    linescore: dict = {}
    if home_runs is not None or away_runs is not None:
        linescore["teams"] = {
            "home": {"runs": home_runs, "hits": 5, "errors": 0},
            "away": {"runs": away_runs, "hits": 4, "errors": 1},
        }
    return {
        "gamePk": game_pk,
        "gameDate": "2026-07-04T18:10:00Z",
        "status": {"detailedState": status},
        "teams": {"home": home_team_info, "away": away_team_info},
        "linescore": linescore,
        "doubleHeader": double_header,
        "gameNumber": game_number,
        "decisions": decisions or {},
    }


def _make_schedule(*games) -> dict:
    return {"dates": [{"games": list(games)}]}


def _make_standings_record(
    div_id: int,
    div_name: str,
    teams: list[tuple[int, str, str, int, int]],
) -> dict:
    """teams: list of (id, abbr, name, wins, losses)"""
    team_records = []
    for team_id, abbr, name, wins, losses in teams:
        total = wins + losses
        pct = wins / total if total else 0.0
        team_records.append(
            {
                "team": {"id": team_id, "abbreviation": abbr, "name": name},
                "wins": wins,
                "losses": losses,
                "winningPercentage": f"{pct:.3f}",
                "gamesBack": "-" if wins >= max(w for _, _, _, w, _ in teams) else "2.0",
                "runDifferential": wins - losses,
                "streak": {"streakCode": "W2"},
                "records": {
                    "splitRecords": [
                        {"type": "home", "wins": wins // 2, "losses": losses // 2},
                        {"type": "away", "wins": wins - wins // 2, "losses": losses - losses // 2},
                        {"type": "lastTen", "wins": 6, "losses": 4},
                    ]
                },
            }
        )
    return {
        "division": {"id": div_id, "nameShort": div_name},
        "teamRecords": team_records,
    }


def _make_transaction(tid: str, type_desc: str) -> dict:
    return {
        "id": tid,
        "typeDesc": type_desc,
        "date": "2026-07-01T00:00:00Z",
        "fromTeam": {"abbreviation": "NYY", "name": "New York Yankees"},
        "person": {"id": 12345, "fullName": "John Doe"},
    }


# ---------------------------------------------------------------------------
# Tests: _GAME_STATUS_MAP coverage
# ---------------------------------------------------------------------------


class TestGameStatusMap:
    normalizer = Normalizer()

    @pytest.mark.parametrize(
        "detail,expected",
        [
            ("Final", GameStatus.final),
            ("Game Over", GameStatus.final),
            ("In Progress", GameStatus.in_progress),
            ("Postponed", GameStatus.postponed),
            ("Delayed", GameStatus.delayed),
            ("Delayed: Rain", GameStatus.delayed),
            ("Suspended", GameStatus.suspended),
            ("Scheduled", GameStatus.scheduled),
            ("Pre-Game", GameStatus.scheduled),
            ("Warmup", GameStatus.scheduled),
        ],
    )
    def test_known_status(self, detail: str, expected: GameStatus) -> None:
        game = _make_game(1, detail)
        result = self.normalizer._parse_game(game)
        assert result.status == expected

    def test_unknown_status_defaults_to_scheduled(self) -> None:
        game = _make_game(1, "Some Unknown State")
        result = self.normalizer._parse_game(game)
        assert result.status == GameStatus.scheduled


# ---------------------------------------------------------------------------
# Tests: individual game parsing
# ---------------------------------------------------------------------------


class TestParseGame:
    normalizer = Normalizer()

    def test_final_game_status_and_runs(self) -> None:
        g = _make_game(100, "Final", home_runs=5, away_runs=3)
        result = self.normalizer._parse_game(g)
        assert result.status == GameStatus.final
        assert result.home.runs == 5
        assert result.away.runs == 3
        assert result.game_id == 100

    def test_scheduled_game_runs_none(self) -> None:
        g = _make_game(101, "Scheduled")
        result = self.normalizer._parse_game(g)
        assert result.status == GameStatus.scheduled
        assert result.home.runs is None
        assert result.away.runs is None

    def test_postponed_game_status(self) -> None:
        g = _make_game(102, "Postponed")
        result = self.normalizer._parse_game(g)
        assert result.status == GameStatus.postponed

    def test_recap_anchor_set(self) -> None:
        g = _make_game(200, "Final", home_runs=4, away_runs=2)
        result = self.normalizer._parse_game(g)
        assert result.recap_anchor == "recap-200"

    def test_doubleheader_true(self) -> None:
        g = _make_game(300, "Final", home_runs=2, away_runs=1, double_header="Y", game_number=1)
        result = self.normalizer._parse_game(g)
        assert result.is_doubleheader is True
        assert result.doubleheader_game_num == 1

    def test_doubleheader_false(self) -> None:
        g = _make_game(301, "Final", home_runs=2, away_runs=1, double_header="N", game_number=1)
        result = self.normalizer._parse_game(g)
        assert result.is_doubleheader is False

    def test_winning_pitcher_parsed(self) -> None:
        g = _make_game(
            400,
            "Final",
            home_runs=5,
            away_runs=3,
            decisions={"winner": {"id": 111, "fullName": "Bob Pitcher"}},
        )
        result = self.normalizer._parse_game(g)
        assert result.winning_pitcher is not None
        assert result.winning_pitcher.player_id == 111
        assert result.winning_pitcher.name == "Bob Pitcher"

    def test_no_decisions_pitchers_none(self) -> None:
        g = _make_game(401, "Scheduled")
        result = self.normalizer._parse_game(g)
        assert result.winning_pitcher is None
        assert result.losing_pitcher is None
        assert result.save_pitcher is None


# ---------------------------------------------------------------------------
# Tests: standings normalization
# ---------------------------------------------------------------------------


class TestNormalizeStandings:
    normalizer = Normalizer()

    def test_single_division_two_teams(self) -> None:
        raw = {
            "records": [
                _make_standings_record(
                    201,
                    "AL East",
                    [
                        (147, "NYY", "New York Yankees", 55, 30),
                        (111, "BOS", "Boston Red Sox", 48, 37),
                    ],
                )
            ]
        }
        standings = self.normalizer._normalize_standings(raw)
        assert len(standings.divisions) == 1
        div = standings.divisions[0]
        assert div.division_name == "AL East"
        assert len(div.rows) == 2
        assert div.rows[0].team_abbr == "NYY"
        assert div.rows[0].wins == 55
        assert div.rows[1].team_abbr == "BOS"

    def test_duplicate_division_deduplicated(self) -> None:
        record = _make_standings_record(
            201,
            "AL East",
            [(147, "NYY", "New York Yankees", 55, 30)],
        )
        raw = {"records": [record, record]}  # same division_id twice
        standings = self.normalizer._normalize_standings(raw)
        assert len(standings.divisions) == 1

    def test_empty_records(self) -> None:
        standings = self.normalizer._normalize_standings({"records": []})
        assert standings.divisions == []
        assert standings.wild_cards == []


# ---------------------------------------------------------------------------
# Tests: transaction normalization
# ---------------------------------------------------------------------------


class TestNormalizeTransactions:
    normalizer = Normalizer()

    def test_deduplication(self) -> None:
        t = _make_transaction("T001", "Trade")
        raw = {"transactions": [t, t]}
        result = self.normalizer._normalize_transactions(raw)
        assert len(result) == 1

    def test_trade_type(self) -> None:
        raw = {"transactions": [_make_transaction("T002", "Trade")]}
        result = self.normalizer._normalize_transactions(raw)
        assert result[0].transaction_type == TransactionType.trade

    def test_released_type(self) -> None:
        raw = {"transactions": [_make_transaction("T003", "Released")]}
        result = self.normalizer._normalize_transactions(raw)
        assert result[0].transaction_type == TransactionType.released

    def test_unknown_type_defaults_to_other(self) -> None:
        raw = {"transactions": [_make_transaction("T004", "Some Weird Transaction")]}
        result = self.normalizer._normalize_transactions(raw)
        assert result[0].transaction_type == TransactionType.other

    def test_all_mapped_types(self) -> None:
        mappings = {
            "Designated for Assignment": TransactionType.dfa,
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
        for type_desc, expected in mappings.items():
            raw = {"transactions": [_make_transaction(f"TX-{type_desc}", type_desc)]}
            result = self.normalizer._normalize_transactions(raw)
            assert result[0].transaction_type == expected, f"Failed for: {type_desc}"

    def test_status_change_to_injured_list_is_injury(self) -> None:
        transaction = _make_transaction("T005", "Status Change")
        transaction["description"] = (
            "New York Mets placed DH Jorge Polanco on the 10-day injured list. "
            "Left ankle bursitis."
        )
        result = self.normalizer._normalize_transactions({"transactions": [transaction]})
        assert result[0].transaction_type == TransactionType.injury

    def test_activation_from_injured_list_remains_activated(self) -> None:
        transaction = _make_transaction("T006", "Status Change")
        transaction["description"] = (
            "Colorado Rockies activated RHP Jaden Hill from the 15-day injured list."
        )
        result = self.normalizer._normalize_transactions({"transactions": [transaction]})
        assert result[0].transaction_type == TransactionType.activated


# ---------------------------------------------------------------------------
# Tests: full normalize() dispatch
# ---------------------------------------------------------------------------


class TestNormalize:
    normalizer = Normalizer()

    def test_normalize_schedule_and_standings(self) -> None:
        raw = {
            "schedule": _make_schedule(_make_game(500, "Final", home_runs=3, away_runs=1)),
            "standings": {
                "records": [
                    _make_standings_record(
                        201,
                        "AL East",
                        [(147, "NYY", "New York Yankees", 55, 30)],
                    )
                ]
            },
        }
        result = self.normalizer.normalize(raw)
        assert isinstance(result, NormalizedData)
        assert len(result.games) == 1
        assert result.games[0].game_id == 500
        assert result.standings is not None
        assert len(result.standings.divisions) == 1

    def test_normalize_empty_raw(self) -> None:
        result = self.normalizer.normalize({})
        assert result.games == []
        assert result.standings is None
        assert result.transactions == []
        assert result.injuries == []

    def test_normalize_transactions(self) -> None:
        raw = {"transactions": {"transactions": [_make_transaction("T100", "Trade")]}}
        result = self.normalizer.normalize(raw)
        assert len(result.transactions) == 1

    def test_normalize_injuries(self) -> None:
        raw = {
            "injuries": {
                "injuries": [
                    {
                        "player": {"id": 9999, "fullName": "Hurt Guy"},
                        "team": {"abbreviation": "LAD"},
                        "notes": "left hamstring strain",
                    }
                ]
            }
        }
        result = self.normalizer.normalize(raw)
        assert len(result.injuries) == 1
        assert result.injuries[0].player_name == "Hurt Guy"
        assert result.injuries[0].team_abbr == "LAD"

    def test_normalize_team_season_leaders_by_club(self) -> None:
        def split(name: str, player_id: int, stat: dict) -> dict:
            return {
                "team": {"id": 143, "abbreviation": "PHI", "name": "Philadelphia Phillies"},
                "player": {"id": player_id, "fullName": name},
                "stat": stat,
            }

        raw = {
            "team_player_stats": {
                "hitting": {
                    "stats": [{"splits": [
                        split("Power Hitter", 1, {"plateAppearances": 300, "avg": ".275", "homeRuns": 31, "rbi": 85, "ops": ".900", "stolenBases": 4}),
                        split("Contact Hitter", 2, {"plateAppearances": 320, "avg": ".315", "homeRuns": 8, "rbi": 42, "ops": ".810", "stolenBases": 19}),
                    ]}]
                },
                "pitching": {
                    "stats": [{"splits": [
                        split("Ace Starter", 3, {"inningsPitched": "140.0", "era": "2.80", "wins": 14, "strikeOuts": 170, "saves": 0, "whip": "1.05"}),
                        split("Closer", 4, {"inningsPitched": "48.0", "era": "2.25", "wins": 3, "strikeOuts": 65, "saves": 32, "whip": "0.98"}),
                    ]}]
                },
            }
        }

        result = self.normalizer.normalize(raw)
        assert len(result.team_season_leaders) == 1
        team = result.team_season_leaders[0]
        assert team.team_abbr == "PHI"
        assert {leader.label: leader.player_name for leader in team.batting}["AVG"] == "Contact Hitter"
        assert {leader.label: leader.player_name for leader in team.batting}["HR"] == "Power Hitter"
        assert {leader.label: leader.player_name for leader in team.pitching}["SV"] == "Closer"

    def test_normalize_mlb_news_as_around_the_league_stories(self) -> None:
        raw = {
            "news": {
                "source": "MLB.com",
                "items": [
                    {
                        "title": "Rookie completes a remarkable journey",
                        "link": "https://www.mlb.com/news/example",
                        "author": "MLB.com Staff",
                        "summary": "A rookie reached the Majors after an unusual path through baseball.",
                    }
                ],
            }
        }

        result = self.normalizer.normalize(raw)
        assert len(result.news_stories) == 1
        assert result.news_stories[0].headline == "Rookie completes a remarkable journey"
        assert result.news_stories[0].source_url == "https://www.mlb.com/news/example"

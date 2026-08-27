# tests/fixtures/builders.py
"""Factory functions that build realistic Edition objects for test scenarios."""

from __future__ import annotations

from datetime import date, datetime, timezone

from src.models.edition import Edition, EditionMetadata, GenerationMetadata
from src.models.game import Game, GameStatus, LinescoreInning, Pitcher, TeamBoxLine, TeamGameLine
from src.models.history import HistoricalItem
from src.models.injuries import Injury, InjuryConfidence, RosterStatus
from src.models.leaders import LeaderEntry, LeagueLeaders, TeamGameLeaders, TeamPerformer
from src.models.standings import (
    DivisionStandings,
    PlayoffStandings,
    Standings,
    StandingsRow,
    WildCardStandings,
)
from src.models.story import GameRecap, Story, StoryType
from src.models.transactions import Transaction, TransactionType

_TEMPLATES_DIR_PATH = None  # not needed here, just model builders

_NOW = datetime(2026, 7, 13, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _metadata(date_str: str, edition_type: str, edition_id: str) -> EditionMetadata:
    return EditionMetadata(
        id=edition_id,
        type=edition_type,  # type: ignore[arg-type]
        date=date_str,
        generated_at=_NOW,
        data_current_through=_NOW,
        timezone="America/New_York",
        status="published",
    )


def _pitcher(player_id: int, name: str, wins: int, losses: int, era: float) -> Pitcher:
    return Pitcher(
        player_id=player_id,
        name=name,
        handedness="R",
        status="confirmed",
        wins=wins,
        losses=losses,
        era=era,
    )


def _team(team_id: int, abbr: str, name: str, runs: int | None = None) -> TeamGameLine:
    return TeamGameLine(
        team_id=team_id,
        team_abbr=abbr,
        team_name=name,
        runs=runs,
        hits=runs + 3 if runs is not None else None,
        errors=0,
    )


def _standings_row(
    team_id: int,
    abbr: str,
    name: str,
    wins: int,
    losses: int,
    gb: float | str = 0.0,
) -> StandingsRow:
    total = wins + losses or 1
    return StandingsRow(
        team_id=team_id,
        team_abbr=abbr,
        team_name=name,
        wins=wins,
        losses=losses,
        pct=round(wins / total, 3),
        games_back=gb,
        last_10="6-4",
        streak="W2",
        home_record=f"{wins // 2}-{losses // 2}",
        away_record=f"{wins - wins // 2}-{losses - losses // 2}",
        run_differential=wins - losses,
    )


def _leader(rank: int, player_id: int, name: str, team: str, pos: str, value: str) -> LeaderEntry:
    return LeaderEntry(
        rank=rank,
        player_id=player_id,
        player_name=name,
        team_abbr=team,
        position=pos,
        value=value,
        games_played=90,
        league="AL",
        qualified=True,
    )


def _make_standings() -> Standings:
    al_east = DivisionStandings(
        division_id=201,
        division_name="AL East",
        rows=[
            _standings_row(147, "NYY", "New York Yankees", 55, 35, 0.0),
            _standings_row(111, "BOS", "Boston Red Sox", 50, 40, 5.0),
            _standings_row(139, "TB", "Tampa Bay Rays", 48, 42, 7.0),
            _standings_row(110, "BAL", "Baltimore Orioles", 45, 45, 10.0),
            _standings_row(141, "TOR", "Toronto Blue Jays", 40, 50, 15.0),
        ],
    )
    al_central = DivisionStandings(
        division_id=202,
        division_name="AL Central",
        rows=[
            _standings_row(145, "CWS", "Chicago White Sox", 52, 38, 0.0),
            _standings_row(142, "MIN", "Minnesota Twins", 50, 40, 2.0),
            _standings_row(116, "DET", "Detroit Tigers", 47, 43, 5.0),
            _standings_row(118, "KC", "Kansas City Royals", 44, 46, 8.0),
            _standings_row(114, "CLE", "Cleveland Guardians", 42, 48, 10.0),
        ],
    )
    al_west = DivisionStandings(
        division_id=200,
        division_name="AL West",
        rows=[
            _standings_row(117, "HOU", "Houston Astros", 58, 32, 0.0),
            _standings_row(133, "OAK", "Oakland Athletics", 48, 42, 10.0),
            _standings_row(140, "TEX", "Texas Rangers", 46, 44, 12.0),
            _standings_row(108, "LAA", "Los Angeles Angels", 40, 50, 18.0),
            _standings_row(136, "SEA", "Seattle Mariners", 38, 52, 20.0),
        ],
    )
    nl_east = DivisionStandings(
        division_id=204,
        division_name="NL East",
        rows=[
            _standings_row(143, "PHI", "Philadelphia Phillies", 57, 33, 0.0),
            _standings_row(121, "NYM", "New York Mets", 52, 38, 5.0),
            _standings_row(144, "ATL", "Atlanta Braves", 50, 40, 7.0),
            _standings_row(120, "WSH", "Washington Nationals", 40, 50, 17.0),
            _standings_row(146, "MIA", "Miami Marlins", 35, 55, 22.0),
        ],
    )
    nl_central = DivisionStandings(
        division_id=205,
        division_name="NL Central",
        rows=[
            _standings_row(112, "CHC", "Chicago Cubs", 53, 37, 0.0),
            _standings_row(158, "MIL", "Milwaukee Brewers", 51, 39, 2.0),
            _standings_row(113, "CIN", "Cincinnati Reds", 48, 42, 5.0),
            _standings_row(134, "PIT", "Pittsburgh Pirates", 42, 48, 11.0),
            _standings_row(138, "STL", "St. Louis Cardinals", 38, 52, 15.0),
        ],
    )
    nl_west = DivisionStandings(
        division_id=203,
        division_name="NL West",
        rows=[
            _standings_row(119, "LAD", "Los Angeles Dodgers", 60, 30, 0.0),
            _standings_row(137, "SF", "San Francisco Giants", 52, 38, 8.0),
            _standings_row(109, "SD", "San Diego Padres", 50, 40, 10.0),
            _standings_row(115, "COL", "Colorado Rockies", 38, 52, 22.0),
            _standings_row(109, "ARI", "Arizona Diamondbacks", 45, 45, 15.0),
        ],
    )
    al_wc = WildCardStandings(
        league="AL",
        rows=[
            _standings_row(111, "BOS", "Boston Red Sox", 50, 40, 0.0).model_copy(
                update={"wild_card_rank": 1, "wild_card_gb": "+2.0"}
            ),
            _standings_row(142, "MIN", "Minnesota Twins", 50, 40, 2.0).model_copy(
                update={"wild_card_rank": 2, "wild_card_gb": "+2.0"}
            ),
            _standings_row(133, "OAK", "Oakland Athletics", 48, 42, 4.0).model_copy(
                update={"wild_card_rank": 3, "wild_card_gb": "-"}
            ),
        ],
    )
    nl_wc = WildCardStandings(
        league="NL",
        rows=[
            _standings_row(121, "NYM", "New York Mets", 52, 38, 0.0).model_copy(
                update={"wild_card_rank": 1, "wild_card_gb": "+2.0"}
            ),
            _standings_row(144, "ATL", "Atlanta Braves", 50, 40, 2.0).model_copy(
                update={"wild_card_rank": 2, "wild_card_gb": "+1.0"}
            ),
            _standings_row(137, "SF", "San Francisco Giants", 52, 38, 2.0).model_copy(
                update={"wild_card_rank": 3, "wild_card_gb": "-"}
            ),
        ],
    )
    al_playoffs = PlayoffStandings(
        league="AL",
        rows=[
            al_west.rows[0].model_copy(update={"playoff_seed": 1, "division_leader": True}),
            al_east.rows[0].model_copy(update={"playoff_seed": 2, "division_leader": True}),
            al_central.rows[0].model_copy(update={"playoff_seed": 3, "division_leader": True}),
            *[
                row.model_copy(update={"playoff_seed": seed})
                for seed, row in enumerate(al_wc.rows, start=4)
            ],
        ],
    )
    nl_playoffs = PlayoffStandings(
        league="NL",
        rows=[
            nl_west.rows[0].model_copy(update={"playoff_seed": 1, "division_leader": True}),
            nl_east.rows[0].model_copy(update={"playoff_seed": 2, "division_leader": True}),
            nl_central.rows[0].model_copy(update={"playoff_seed": 3, "division_leader": True}),
            *[
                row.model_copy(update={"playoff_seed": seed})
                for seed, row in enumerate(nl_wc.rows, start=4)
            ],
        ],
    )
    return Standings(
        divisions=[al_east, al_central, al_west, nl_east, nl_central, nl_west],
        playoff_pictures=[al_playoffs, nl_playoffs],
        wild_cards=[al_wc, nl_wc],
    )


def _make_league_leaders() -> LeagueLeaders:
    batting = {
        "avg": [
            _leader(1, 6480, "Juan Soto", "NYY", "RF", ".342"),
            _leader(2, 5870, "Freddie Freeman", "LAD", "1B", ".335"),
            _leader(3, 7220, "Corey Seager", "TEX", "SS", ".328"),
            _leader(4, 7890, "Aaron Judge", "NYY", "RF", ".321"),
            _leader(5, 6200, "Yordan Alvarez", "HOU", "DH", ".318"),
            _leader(6, 5550, "Matt Olson", "ATL", "1B", ".314"),
            _leader(7, 7100, "José Ramírez", "CLE", "3B", ".311"),
            _leader(8, 6750, "Paul Goldschmidt", "STL", "1B", ".308"),
            _leader(9, 6910, "Rafael Devers", "BOS", "3B", ".305"),
            _leader(10, 7350, "Trea Turner", "PHI", "SS", ".302"),
        ],
        "hr": [
            _leader(1, 7890, "Aaron Judge", "NYY", "RF", "32"),
            _leader(2, 6200, "Pete Alonso", "NYM", "1B", "28"),
            _leader(3, 5550, "Matt Olson", "ATL", "1B", "27"),
            _leader(4, 6480, "Yordan Alvarez", "HOU", "DH", "25"),
            _leader(5, 7120, "Kyle Schwarber", "PHI", "LF", "24"),
            _leader(6, 6310, "Adolis García", "TEX", "RF", "23"),
            _leader(7, 7450, "Bryce Harper", "PHI", "1B", "22"),
            _leader(8, 6620, "Shohei Ohtani", "LAD", "DH", "21"),
            _leader(9, 7780, "Vladimir Guerrero Jr.", "TOR", "1B", "20"),
            _leader(10, 6090, "Bo Bichette", "TOR", "SS", "19"),
        ],
        "rbi": [
            _leader(1, 7890, "Aaron Judge", "NYY", "RF", "88"),
            _leader(2, 5550, "Matt Olson", "ATL", "1B", "82"),
            _leader(3, 6200, "Pete Alonso", "NYM", "1B", "79"),
            _leader(4, 6480, "Yordan Alvarez", "HOU", "DH", "76"),
            _leader(5, 7450, "Bryce Harper", "PHI", "1B", "73"),
            _leader(6, 7100, "José Ramírez", "CLE", "3B", ".70"),
            _leader(7, 6620, "Shohei Ohtani", "LAD", "DH", "68"),
            _leader(8, 7780, "Vladimir Guerrero Jr.", "TOR", "1B", "65"),
            _leader(9, 7120, "Kyle Schwarber", "PHI", "LF", "63"),
            _leader(10, 6910, "Rafael Devers", "BOS", "3B", "61"),
        ],
        "obp": [
            _leader(1, 6480, "Juan Soto", "NYY", "RF", ".448"),
            _leader(2, 7890, "Aaron Judge", "NYY", "RF", ".430"),
            _leader(3, 5870, "Freddie Freeman", "LAD", "1B", ".418"),
            _leader(4, 7450, "Bryce Harper", "PHI", "1B", ".412"),
            _leader(5, 6620, "Shohei Ohtani", "LAD", "DH", ".405"),
            _leader(6, 7220, "Corey Seager", "TEX", "SS", ".398"),
            _leader(7, 7100, "José Ramírez", "CLE", "3B", ".391"),
            _leader(8, 6750, "Paul Goldschmidt", "STL", "1B", ".385"),
            _leader(9, 6910, "Rafael Devers", "BOS", "3B", ".381"),
            _leader(10, 7350, "Trea Turner", "PHI", "SS", ".377"),
        ],
        "slg": [
            _leader(1, 7890, "Aaron Judge", "NYY", "RF", ".652"),
            _leader(2, 6620, "Shohei Ohtani", "LAD", "DH", ".628"),
            _leader(3, 6480, "Yordan Alvarez", "HOU", "DH", ".609"),
            _leader(4, 7450, "Bryce Harper", "PHI", "1B", ".595"),
            _leader(5, 5550, "Matt Olson", "ATL", "1B", ".580"),
            _leader(6, 7120, "Kyle Schwarber", "PHI", "LF", ".571"),
            _leader(7, 6200, "Pete Alonso", "NYM", "1B", ".562"),
            _leader(8, 6310, "Adolis García", "TEX", "RF", ".548"),
            _leader(9, 7100, "José Ramírez", "CLE", "3B", ".535"),
            _leader(10, 5870, "Freddie Freeman", "LAD", "1B", ".522"),
        ],
        "ops": [
            _leader(1, 7890, "Aaron Judge", "NYY", "RF", "1.082"),
            _leader(2, 6480, "Juan Soto", "NYY", "RF", "1.051"),
            _leader(3, 6620, "Shohei Ohtani", "LAD", "DH", "1.033"),
            _leader(4, 7450, "Bryce Harper", "PHI", "1B", "1.007"),
            _leader(5, 6480, "Yordan Alvarez", "HOU", "DH", ".992"),
            _leader(6, 5870, "Freddie Freeman", "LAD", "1B", ".975"),
            _leader(7, 7120, "Kyle Schwarber", "PHI", "LF", ".963"),
            _leader(8, 5550, "Matt Olson", "ATL", "1B", ".950"),
            _leader(9, 7100, "José Ramírez", "CLE", "3B", ".938"),
            _leader(10, 7220, "Corey Seager", "TEX", "SS", ".921"),
        ],
        "r": [
            _leader(1, 7890, "Aaron Judge", "NYY", "RF", "79"),
            _leader(2, 6480, "Juan Soto", "NYY", "RF", "75"),
            _leader(3, 7350, "Trea Turner", "PHI", "SS", "72"),
            _leader(4, 6620, "Shohei Ohtani", "LAD", "DH", "70"),
            _leader(5, 7100, "José Ramírez", "CLE", "3B", "68"),
            _leader(6, 5870, "Freddie Freeman", "LAD", "1B", "65"),
            _leader(7, 7450, "Bryce Harper", "PHI", "1B", "63"),
            _leader(8, 6910, "Rafael Devers", "BOS", "3B", "61"),
            _leader(9, 7780, "Vladimir Guerrero Jr.", "TOR", "1B", "59"),
            _leader(10, 7220, "Corey Seager", "TEX", "SS", "57"),
        ],
        "h": [
            _leader(1, 5870, "Freddie Freeman", "LAD", "1B", "118"),
            _leader(2, 7350, "Trea Turner", "PHI", "SS", "115"),
            _leader(3, 7220, "Corey Seager", "TEX", "SS", "112"),
            _leader(4, 6750, "Paul Goldschmidt", "STL", "1B", "109"),
            _leader(5, 7100, "José Ramírez", "CLE", "3B", "107"),
            _leader(6, 6910, "Rafael Devers", "BOS", "3B", "105"),
            _leader(7, 6480, "Juan Soto", "NYY", "RF", "103"),
            _leader(8, 7780, "Vladimir Guerrero Jr.", "TOR", "1B", "101"),
            _leader(9, 7890, "Aaron Judge", "NYY", "RF", "98"),
            _leader(10, 6090, "Bo Bichette", "TOR", "SS", "96"),
        ],
        "sb": [
            _leader(1, 7350, "Trea Turner", "PHI", "SS", "32"),
            _leader(2, 8010, "Elly De La Cruz", "CIN", "SS", "29"),
            _leader(3, 7980, "Ronald Acuña Jr.", "ATL", "CF", "27"),
            _leader(4, 7520, "Bobby Witt Jr.", "KC", "SS", "25"),
            _leader(5, 7660, "Cedric Mullins", "BAL", "CF", "22"),
            _leader(6, 7100, "José Ramírez", "CLE", "3B", "20"),
            _leader(7, 6090, "Bo Bichette", "TOR", "SS", "18"),
            _leader(8, 7230, "Jazz Chisholm Jr.", "NYY", "2B", "17"),
            _leader(9, 6840, "Starling Marte", "NYM", "RF", "16"),
            _leader(10, 7410, "Julio Rodríguez", "SEA", "CF", "15"),
        ],
        "doubles": [
            _leader(1, 5870, "Freddie Freeman", "LAD", "1B", "28"),
            _leader(2, 7100, "José Ramírez", "CLE", "3B", "26"),
            _leader(3, 7220, "Corey Seager", "TEX", "SS", "25"),
            _leader(4, 6910, "Rafael Devers", "BOS", "3B", "24"),
            _leader(5, 6750, "Paul Goldschmidt", "STL", "1B", "23"),
            _leader(6, 7450, "Bryce Harper", "PHI", "1B", "22"),
            _leader(7, 7780, "Vladimir Guerrero Jr.", "TOR", "1B", "21"),
            _leader(8, 6200, "Pete Alonso", "NYM", "1B", "20"),
            _leader(9, 7350, "Trea Turner", "PHI", "SS", "19"),
            _leader(10, 6480, "Juan Soto", "NYY", "RF", "18"),
        ],
        "bb": [
            _leader(1, 6480, "Juan Soto", "NYY", "RF", "82"),
            _leader(2, 7890, "Aaron Judge", "NYY", "RF", "76"),
            _leader(3, 7450, "Bryce Harper", "PHI", "1B", "71"),
            _leader(4, 6620, "Shohei Ohtani", "LAD", "DH", "67"),
            _leader(5, 5870, "Freddie Freeman", "LAD", "1B", "63"),
            _leader(6, 7120, "Kyle Schwarber", "PHI", "LF", "60"),
            _leader(7, 5550, "Matt Olson", "ATL", "1B", "57"),
            _leader(8, 7100, "José Ramírez", "CLE", "3B", "54"),
            _leader(9, 6750, "Paul Goldschmidt", "STL", "1B", "51"),
            _leader(10, 6910, "Rafael Devers", "BOS", "3B", "48"),
        ],
        "so": [
            _leader(1, 7120, "Kyle Schwarber", "PHI", "LF", "142"),
            _leader(2, 6200, "Pete Alonso", "NYM", "1B", "135"),
            _leader(3, 6310, "Adolis García", "TEX", "RF", "129"),
            _leader(4, 7890, "Aaron Judge", "NYY", "RF", "124"),
            _leader(5, 5550, "Matt Olson", "ATL", "1B", "119"),
            _leader(6, 7780, "Vladimir Guerrero Jr.", "TOR", "1B", "113"),
            _leader(7, 8010, "Elly De La Cruz", "CIN", "SS", "108"),
            _leader(8, 6480, "Yordan Alvarez", "HOU", "DH", "103"),
            _leader(9, 7410, "Julio Rodríguez", "SEA", "CF", "98"),
            _leader(10, 6090, "Bo Bichette", "TOR", "SS", "94"),
        ],
    }
    pitching = {
        "era": [
            _leader(1, 4320, "Gerrit Cole", "NYY", "SP", "2.41"),
            _leader(2, 5100, "Zack Wheeler", "PHI", "SP", "2.58"),
            _leader(3, 4810, "Spencer Strider", "ATL", "SP", "2.71"),
            _leader(4, 6650, "Logan Webb", "SF", "SP", "2.84"),
            _leader(5, 7030, "Tarik Skubal", "DET", "SP", "2.97"),
            _leader(6, 5980, "Corbin Burnes", "BAL", "SP", "3.05"),
            _leader(7, 6120, "Sandy Alcantara", "MIA", "SP", "3.14"),
            _leader(8, 6430, "Dylan Cease", "SD", "SP", "3.22"),
            _leader(9, 5760, "Framber Valdez", "HOU", "SP", "3.31"),
            _leader(10, 6270, "Pablo López", "MIN", "SP", "3.39"),
        ],
        "wins": [
            _leader(1, 4320, "Gerrit Cole", "NYY", "SP", "13"),
            _leader(2, 5100, "Zack Wheeler", "PHI", "SP", "12"),
            _leader(3, 6650, "Logan Webb", "SF", "SP", "11"),
            _leader(4, 4810, "Spencer Strider", "ATL", "SP", "11"),
            _leader(5, 7030, "Tarik Skubal", "DET", "SP", "10"),
            _leader(6, 5980, "Corbin Burnes", "BAL", "SP", "10"),
            _leader(7, 5760, "Framber Valdez", "HOU", "SP", "10"),
            _leader(8, 6120, "Sandy Alcantara", "MIA", "SP", "9"),
            _leader(9, 6430, "Dylan Cease", "SD", "SP", "9"),
            _leader(10, 6270, "Pablo López", "MIN", "SP", "9"),
        ],
        "k": [
            _leader(1, 4810, "Spencer Strider", "ATL", "SP", "158"),
            _leader(2, 4320, "Gerrit Cole", "NYY", "SP", "147"),
            _leader(3, 5100, "Zack Wheeler", "PHI", "SP", "141"),
            _leader(4, 7030, "Tarik Skubal", "DET", "SP", "135"),
            _leader(5, 6430, "Dylan Cease", "SD", "SP", "129"),
            _leader(6, 5980, "Corbin Burnes", "BAL", "SP", "123"),
            _leader(7, 6650, "Logan Webb", "SF", "SP", "117"),
            _leader(8, 6270, "Pablo López", "MIN", "SP", "112"),
            _leader(9, 5760, "Framber Valdez", "HOU", "SP", "108"),
            _leader(10, 6120, "Sandy Alcantara", "MIA", "SP", "104"),
        ],
        "saves": [
            _leader(1, 8100, "Emmanuel Clase", "CLE", "RP", "28"),
            _leader(2, 7850, "Ryan Helsley", "STL", "RP", "25"),
            _leader(3, 8200, "Josh Hader", "HOU", "RP", "24"),
            _leader(4, 8050, "Alexis Díaz", "CIN", "RP", "22"),
            _leader(5, 7920, "David Bednar", "PIT", "RP", "20"),
            _leader(6, 7770, "Andrés Muñoz", "SEA", "RP", "19"),
            _leader(7, 8300, "Jordan Romano", "TOR", "RP", "18"),
            _leader(8, 8150, "Clay Holmes", "NYY", "RP", "17"),
            _leader(9, 7690, "Kenley Jansen", "BOS", "RP", "16"),
            _leader(10, 8400, "Paul Sewald", "ARI", "RP", "15"),
        ],
        "whip": [
            _leader(1, 4320, "Gerrit Cole", "NYY", "SP", "0.92"),
            _leader(2, 7030, "Tarik Skubal", "DET", "SP", "0.98"),
            _leader(3, 5100, "Zack Wheeler", "PHI", "SP", "1.01"),
            _leader(4, 4810, "Spencer Strider", "ATL", "SP", "1.05"),
            _leader(5, 6650, "Logan Webb", "SF", "SP", "1.08"),
            _leader(6, 5980, "Corbin Burnes", "BAL", "SP", "1.11"),
            _leader(7, 6120, "Sandy Alcantara", "MIA", "SP", "1.14"),
            _leader(8, 5760, "Framber Valdez", "HOU", "SP", "1.17"),
            _leader(9, 6270, "Pablo López", "MIN", "SP", "1.20"),
            _leader(10, 6430, "Dylan Cease", "SD", "SP", "1.23"),
        ],
    }
    return LeagueLeaders(batting=batting, pitching=pitching)


def _make_transaction(
    tid: str,
    team_abbr: str,
    team_name: str,
    player: str,
    pid: int,
    ttype: TransactionType,
    explanation: str,
) -> Transaction:
    return Transaction(
        transaction_id=tid,
        team_abbr=team_abbr,
        team_name=team_name,
        player_name=player,
        player_id=pid,
        transaction_type=ttype,
        effective_date=date(2026, 7, 13),
        explanation=explanation,
        source_timestamp=_NOW,
    )


def _make_injury(player_id: int, name: str, team: str, desc: str, status: RosterStatus) -> Injury:
    return Injury(
        player_id=player_id,
        player_name=name,
        team_abbr=team,
        injury_description=desc,
        roster_status=status,
        date_of_injury=date(2026, 7, 1),
        confidence_level=InjuryConfidence.confirmed,
        latest_update=f"{name} remains day-to-day.",
        update_timestamp=_NOW,
    )


def _make_game_final(
    game_id: int,
    away_abbr: str,
    away_name: str,
    away_id: int,
    away_runs: int,
    home_abbr: str,
    home_name: str,
    home_id: int,
    home_runs: int,
    tags: list[str] | None = None,
) -> Game:
    return Game(
        game_id=game_id,
        game_date="2026-07-13",
        status=GameStatus.final,
        home=_team(home_id, home_abbr, home_name, home_runs),
        away=_team(away_id, away_abbr, away_name, away_runs),
        linescore=[
            LinescoreInning(inning=i, away_runs=1 if i == 1 else 0, home_runs=1 if i == 7 else 0)
            for i in range(1, 10)
        ],
        winning_pitcher=_pitcher(4320, "Gerrit Cole", 13, 3, 2.41),
        losing_pitcher=_pitcher(5100, "Chris Sale", 8, 6, 3.22),
        venue_name="Yankee Stadium",
        venue_city="Bronx",
        attendance=45_231,
        time_of_game="3:02",
        tv_broadcasts=["YES", "NESN"],
        tags=tags or [],
    )


def _make_game_scheduled(
    game_id: int,
    away_abbr: str,
    away_name: str,
    away_id: int,
    home_abbr: str,
    home_name: str,
    home_id: int,
    game_time: str = "7:05 PM",
) -> Game:
    return Game(
        game_id=game_id,
        game_date="2026-07-13",
        status=GameStatus.scheduled,
        home=_team(home_id, home_abbr, home_name),
        away=_team(away_id, away_abbr, away_name),
        game_time_et=game_time,
        home_probable_pitcher=_pitcher(4320, "Gerrit Cole", 13, 3, 2.41),
        away_probable_pitcher=_pitcher(5100, "Zack Wheeler", 12, 4, 2.58),
        venue_name="Wrigley Field",
        venue_city="Chicago",
        tv_broadcasts=["ESPN"],
        weather_description="Partly cloudy, 78°F",
    )


def _make_game_in_progress(
    game_id: int,
    away_abbr: str,
    away_name: str,
    away_id: int,
    away_runs: int,
    home_abbr: str,
    home_name: str,
    home_id: int,
    home_runs: int,
    inning: int = 6,
) -> Game:
    return Game(
        game_id=game_id,
        game_date="2026-07-13",
        status=GameStatus.in_progress,
        inning=inning,
        inning_state="Top",
        home=_team(home_id, home_abbr, home_name, home_runs),
        away=_team(away_id, away_abbr, away_name, away_runs),
        linescore=[
            LinescoreInning(inning=i, away_runs=1 if i == 2 else 0, home_runs=1 if i == 4 else 0)
            for i in range(1, inning + 1)
        ],
        venue_name="Fenway Park",
        venue_city="Boston",
        tv_broadcasts=["NESN"],
    )


# ---------------------------------------------------------------------------
# Public builder functions
# ---------------------------------------------------------------------------


def build_full_slate_edition(date_str: str = "2026-07-13") -> Edition:
    """15 games, mix of final/in-progress/scheduled, all sections populated."""
    games: list[Game] = [
        # 6 final games
        _make_game_final(
            748293, "BOS", "Boston Red Sox", 111, 3, "NYY", "New York Yankees", 147, 5
        ),
        _make_game_final(748294, "CHC", "Chicago Cubs", 112, 2, "MIL", "Milwaukee Brewers", 158, 4),
        _make_game_final(
            748295, "ATL", "Atlanta Braves", 144, 6, "PHI", "Philadelphia Phillies", 143, 5
        ),
        _make_game_final(
            748296, "SF", "San Francisco Giants", 137, 1, "LAD", "Los Angeles Dodgers", 119, 3
        ),
        _make_game_final(748297, "HOU", "Houston Astros", 117, 7, "TEX", "Texas Rangers", 140, 4),
        _make_game_final(
            748298, "CLE", "Cleveland Guardians", 114, 0, "DET", "Detroit Tigers", 116, 5
        ),
        # 3 in-progress
        _make_game_in_progress(
            748299, "NYM", "New York Mets", 121, 2, "WSH", "Washington Nationals", 120, 3
        ),
        _make_game_in_progress(
            748300, "MIN", "Minnesota Twins", 142, 1, "KC", "Kansas City Royals", 118, 1
        ),
        _make_game_in_progress(
            748301, "SD", "San Diego Padres", 135, 3, "COL", "Colorado Rockies", 115, 2
        ),
        # 6 scheduled
        _make_game_scheduled(
            748302, "TOR", "Toronto Blue Jays", 141, "BAL", "Baltimore Orioles", 110
        ),
        _make_game_scheduled(
            748303, "OAK", "Oakland Athletics", 133, "SEA", "Seattle Mariners", 136
        ),
        _make_game_scheduled(
            748304, "LAA", "Los Angeles Angels", 108, "CWS", "Chicago White Sox", 145
        ),
        _make_game_scheduled(
            748305, "MIA", "Miami Marlins", 146, "STL", "St. Louis Cardinals", 138
        ),
        _make_game_scheduled(
            748306, "PIT", "Pittsburgh Pirates", 134, "CIN", "Cincinnati Reds", 113
        ),
        _make_game_scheduled(
            748307, "TB", "Tampa Bay Rays", 139, "BOS", "Boston Red Sox", 111, "10:10 PM"
        ),
    ]

    # Add box score data to game 748293 (BOS at NYY)
    games[0] = games[0].model_copy(
        update={
            "batting_lines": {
                "BOS": [
                    TeamBoxLine(
                        player_name="Jarren Duran",
                        player_id=9001,
                        ab=4,
                        r=1,
                        h=2,
                        rbi=1,
                        bb=0,
                        k=1,
                        avg=".298",
                    ),
                    TeamBoxLine(
                        player_name="Rafael Devers",
                        player_id=6910,
                        ab=4,
                        r=1,
                        h=1,
                        rbi=1,
                        bb=0,
                        k=2,
                        avg=".305",
                    ),
                    TeamBoxLine(
                        player_name="Justin Turner",
                        player_id=9002,
                        ab=3,
                        r=0,
                        h=1,
                        rbi=0,
                        bb=1,
                        k=1,
                        avg=".272",
                    ),
                    TeamBoxLine(
                        player_name="Masataka Yoshida",
                        player_id=9003,
                        ab=4,
                        r=0,
                        h=1,
                        rbi=1,
                        bb=0,
                        k=0,
                        avg=".285",
                    ),
                    TeamBoxLine(
                        player_name="Adam Duvall",
                        player_id=9004,
                        ab=3,
                        r=1,
                        h=0,
                        rbi=0,
                        bb=1,
                        k=2,
                        avg=".241",
                    ),
                    TeamBoxLine(
                        player_name="Enrique Hernández",
                        player_id=9005,
                        ab=4,
                        r=0,
                        h=1,
                        rbi=0,
                        bb=0,
                        k=1,
                        avg=".255",
                    ),
                    TeamBoxLine(
                        player_name="Reese McGuire",
                        player_id=9006,
                        ab=3,
                        r=0,
                        h=1,
                        rbi=0,
                        bb=0,
                        k=1,
                        avg=".239",
                    ),
                    TeamBoxLine(
                        player_name="Trevor Story",
                        player_id=9007,
                        ab=3,
                        r=0,
                        h=0,
                        rbi=0,
                        bb=0,
                        k=2,
                        avg=".231",
                    ),
                    TeamBoxLine(
                        player_name="Rob Refsnyder",
                        player_id=9008,
                        ab=3,
                        r=0,
                        h=1,
                        rbi=0,
                        bb=0,
                        k=1,
                        avg=".263",
                    ),
                ],
                "NYY": [
                    TeamBoxLine(
                        player_name="Aaron Judge",
                        player_id=7890,
                        ab=4,
                        r=2,
                        h=2,
                        rbi=2,
                        bb=1,
                        k=1,
                        avg=".321",
                    ),
                    TeamBoxLine(
                        player_name="Juan Soto",
                        player_id=6480,
                        ab=4,
                        r=1,
                        h=2,
                        rbi=1,
                        bb=1,
                        k=0,
                        avg=".342",
                    ),
                    TeamBoxLine(
                        player_name="Gleyber Torres",
                        player_id=9010,
                        ab=4,
                        r=1,
                        h=2,
                        rbi=1,
                        bb=0,
                        k=1,
                        avg=".271",
                    ),
                    TeamBoxLine(
                        player_name="Anthony Rizzo",
                        player_id=9011,
                        ab=3,
                        r=0,
                        h=1,
                        rbi=1,
                        bb=1,
                        k=1,
                        avg=".244",
                    ),
                    TeamBoxLine(
                        player_name="Jazz Chisholm Jr.",
                        player_id=7230,
                        ab=4,
                        r=1,
                        h=1,
                        rbi=0,
                        bb=0,
                        k=2,
                        avg=".258",
                    ),
                    TeamBoxLine(
                        player_name="Alex Verdugo",
                        player_id=9012,
                        ab=3,
                        r=0,
                        h=1,
                        rbi=0,
                        bb=0,
                        k=1,
                        avg=".267",
                    ),
                    TeamBoxLine(
                        player_name="Jose Trevino",
                        player_id=9013,
                        ab=3,
                        r=0,
                        h=0,
                        rbi=0,
                        bb=0,
                        k=1,
                        avg=".221",
                    ),
                    TeamBoxLine(
                        player_name="Oswald Peraza",
                        player_id=9014,
                        ab=3,
                        r=0,
                        h=1,
                        rbi=0,
                        bb=0,
                        k=0,
                        avg=".248",
                    ),
                    TeamBoxLine(
                        player_name="Isiah Kiner-Falefa",
                        player_id=9015,
                        ab=2,
                        r=0,
                        h=0,
                        rbi=0,
                        bb=1,
                        k=1,
                        avg=".233",
                    ),
                ],
            },
            "pitching_lines": {
                "BOS": [
                    TeamBoxLine(
                        player_name="Chris Sale",
                        player_id=5100,
                        ip="6.0",
                        hits_allowed=7,
                        r=3,
                        er=3,
                        bb_allowed=2,
                        k_pitched=8,
                        era="3.22",
                        decision="L",
                    ),
                    TeamBoxLine(
                        player_name="John Schreiber",
                        player_id=9020,
                        ip="1.0",
                        hits_allowed=1,
                        r=1,
                        er=1,
                        bb_allowed=0,
                        k_pitched=1,
                        era="3.45",
                    ),
                    TeamBoxLine(
                        player_name="Garrett Whitlock",
                        player_id=9021,
                        ip="1.0",
                        hits_allowed=1,
                        r=1,
                        er=1,
                        bb_allowed=1,
                        k_pitched=2,
                        era="3.72",
                    ),
                ],
                "NYY": [
                    TeamBoxLine(
                        player_name="Gerrit Cole",
                        player_id=4320,
                        ip="7.0",
                        hits_allowed=7,
                        r=3,
                        er=2,
                        bb_allowed=1,
                        k_pitched=9,
                        era="2.41",
                        decision="W",
                    ),
                    TeamBoxLine(
                        player_name="Clay Holmes",
                        player_id=6650,
                        ip="1.0",
                        hits_allowed=0,
                        r=0,
                        er=0,
                        bb_allowed=1,
                        k_pitched=1,
                        era="2.85",
                    ),
                    TeamBoxLine(
                        player_name="Jonathan Loáisiga",
                        player_id=9022,
                        ip="1.0",
                        hits_allowed=0,
                        r=0,
                        er=0,
                        bb_allowed=0,
                        k_pitched=2,
                        era="2.91",
                        decision="S",
                    ),
                ],
            },
        }
    )

    # Add box score data to game 748297 (HOU at TEX)
    games[4] = games[4].model_copy(
        update={
            "batting_lines": {
                "HOU": [
                    TeamBoxLine(
                        player_name="José Altuve",
                        player_id=9030,
                        ab=4,
                        r=2,
                        h=3,
                        rbi=2,
                        bb=1,
                        k=0,
                        avg=".311",
                    ),
                    TeamBoxLine(
                        player_name="Yordan Alvarez",
                        player_id=6480,
                        ab=4,
                        r=2,
                        h=2,
                        rbi=3,
                        bb=1,
                        k=1,
                        avg=".318",
                    ),
                    TeamBoxLine(
                        player_name="Alex Bregman",
                        player_id=9031,
                        ab=4,
                        r=1,
                        h=2,
                        rbi=1,
                        bb=0,
                        k=1,
                        avg=".288",
                    ),
                    TeamBoxLine(
                        player_name="Kyle Tucker",
                        player_id=9032,
                        ab=4,
                        r=1,
                        h=1,
                        rbi=1,
                        bb=0,
                        k=1,
                        avg=".281",
                    ),
                    TeamBoxLine(
                        player_name="Michael Brantley",
                        player_id=9033,
                        ab=3,
                        r=1,
                        h=2,
                        rbi=0,
                        bb=1,
                        k=0,
                        avg=".295",
                    ),
                    TeamBoxLine(
                        player_name="Martin Maldonado",
                        player_id=9034,
                        ab=3,
                        r=0,
                        h=0,
                        rbi=0,
                        bb=0,
                        k=2,
                        avg=".198",
                    ),
                    TeamBoxLine(
                        player_name="Mauricio Dubón",
                        player_id=9035,
                        ab=4,
                        r=0,
                        h=1,
                        rbi=0,
                        bb=0,
                        k=1,
                        avg=".248",
                    ),
                    TeamBoxLine(
                        player_name="Jeremy Peña",
                        player_id=9036,
                        ab=3,
                        r=0,
                        h=1,
                        rbi=0,
                        bb=1,
                        k=1,
                        avg=".252",
                    ),
                    TeamBoxLine(
                        player_name="Chas McCormick",
                        player_id=9037,
                        ab=3,
                        r=0,
                        h=0,
                        rbi=0,
                        bb=0,
                        k=2,
                        avg=".239",
                    ),
                ],
                "TEX": [
                    TeamBoxLine(
                        player_name="Corey Seager",
                        player_id=7220,
                        ab=4,
                        r=2,
                        h=2,
                        rbi=1,
                        bb=0,
                        k=1,
                        avg=".328",
                    ),
                    TeamBoxLine(
                        player_name="Marcus Semien",
                        player_id=9040,
                        ab=4,
                        r=1,
                        h=2,
                        rbi=1,
                        bb=0,
                        k=1,
                        avg=".271",
                    ),
                    TeamBoxLine(
                        player_name="Adolis García",
                        player_id=6310,
                        ab=4,
                        r=1,
                        h=1,
                        rbi=2,
                        bb=0,
                        k=2,
                        avg=".259",
                    ),
                    TeamBoxLine(
                        player_name="Josh Jung",
                        player_id=9041,
                        ab=3,
                        r=0,
                        h=1,
                        rbi=0,
                        bb=1,
                        k=1,
                        avg=".265",
                    ),
                    TeamBoxLine(
                        player_name="Nathaniel Lowe",
                        player_id=9042,
                        ab=4,
                        r=0,
                        h=1,
                        rbi=0,
                        bb=0,
                        k=1,
                        avg=".276",
                    ),
                    TeamBoxLine(
                        player_name="Travis Jankowski",
                        player_id=9043,
                        ab=3,
                        r=0,
                        h=0,
                        rbi=0,
                        bb=0,
                        k=2,
                        avg=".231",
                    ),
                    TeamBoxLine(
                        player_name="Jonah Heim",
                        player_id=9044,
                        ab=3,
                        r=0,
                        h=1,
                        rbi=0,
                        bb=0,
                        k=1,
                        avg=".244",
                    ),
                    TeamBoxLine(
                        player_name="Leody Taveras",
                        player_id=9045,
                        ab=3,
                        r=0,
                        h=0,
                        rbi=0,
                        bb=0,
                        k=2,
                        avg=".225",
                    ),
                    TeamBoxLine(
                        player_name="Ezequiel Durán",
                        player_id=9046,
                        ab=3,
                        r=0,
                        h=0,
                        rbi=0,
                        bb=1,
                        k=1,
                        avg=".238",
                    ),
                ],
            },
            "pitching_lines": {
                "HOU": [
                    TeamBoxLine(
                        player_name="Framber Valdez",
                        player_id=5760,
                        ip="7.0",
                        hits_allowed=6,
                        r=4,
                        er=4,
                        bb_allowed=2,
                        k_pitched=7,
                        era="3.31",
                        decision="W",
                    ),
                    TeamBoxLine(
                        player_name="Bryan Abreu",
                        player_id=9050,
                        ip="1.0",
                        hits_allowed=0,
                        r=0,
                        er=0,
                        bb_allowed=0,
                        k_pitched=1,
                        era="2.45",
                    ),
                    TeamBoxLine(
                        player_name="Josh Hader",
                        player_id=8200,
                        ip="1.0",
                        hits_allowed=0,
                        r=0,
                        er=0,
                        bb_allowed=0,
                        k_pitched=2,
                        era="1.98",
                        decision="S",
                    ),
                ],
                "TEX": [
                    TeamBoxLine(
                        player_name="Nathan Eovaldi",
                        player_id=9051,
                        ip="5.1",
                        hits_allowed=8,
                        r=5,
                        er=5,
                        bb_allowed=2,
                        k_pitched=5,
                        era="3.88",
                        decision="L",
                    ),
                    TeamBoxLine(
                        player_name="Josh Sborz",
                        player_id=9052,
                        ip="1.2",
                        hits_allowed=2,
                        r=2,
                        er=2,
                        bb_allowed=1,
                        k_pitched=2,
                        era="4.15",
                    ),
                    TeamBoxLine(
                        player_name="Brock Burke",
                        player_id=9053,
                        ip="2.0",
                        hits_allowed=1,
                        r=0,
                        er=0,
                        bb_allowed=0,
                        k_pitched=3,
                        era="3.21",
                    ),
                ],
            },
        }
    )

    lead_story = Story(
        headline="Yankees Walk Off Red Sox in Bronx Thriller",
        deck="A late-inning rally gives New York the series lead.",
        byline="SportzBallz Staff",
        paragraphs=[
            "The New York Yankees rallied for two runs in the eighth inning to defeat the Boston Red Sox 5-3 on Monday night at Yankee Stadium.",
            "Aaron Judge delivered the go-ahead RBI single with two outs, extending his team-leading RBI total to 88 on the season.",
            "Gerrit Cole earned his 13th win, striking out nine over seven innings while allowing just two earned runs.",
        ],
        story_type=StoryType.lead,
        teams=["NYY", "BOS"],
        players=["Aaron Judge", "Gerrit Cole"],
        facts_used=["game:748293", "player:7890", "player:4320"],
        source_data_references=["game:748293"],
    )

    secondary_stories = [
        Story(
            headline="Astros Power Past Rangers to Extend Division Lead",
            deck="Houston wins its fifth straight game, now 8.5 games ahead.",
            byline="SportzBallz Staff",
            paragraphs=[
                "The Houston Astros defeated the Texas Rangers 7-4, extending their AL West lead."
            ],
            story_type=StoryType.secondary,
            teams=["HOU", "TEX"],
        ),
        Story(
            headline="Dodgers Bullpen Holds Down Giants in Series Opener",
            deck="Los Angeles wins 3-1 as relievers retire the final nine batters.",
            byline="SportzBallz Staff",
            paragraphs=[
                "The Los Angeles Dodgers bullpen was dominant in a 3-1 win over San Francisco."
            ],
            story_type=StoryType.secondary,
            teams=["LAD", "SF"],
        ),
        Story(
            headline="Tigers Blank Guardians as Skubal Dominates",
            deck="Detroit's ace allows zero runs over eight innings.",
            byline="SportzBallz Staff",
            paragraphs=[
                "Tarik Skubal pitched eight shutout innings as Detroit beat Cleveland 5-0."
            ],
            story_type=StoryType.secondary,
            teams=["DET", "CLE"],
        ),
    ]

    game_recaps = [
        GameRecap(
            game_id=748293,
            final_score="NYY 5, BOS 3",
            headline="Yankees Walk Off Red Sox in Bronx Thriller",
            deck="Judge drives in go-ahead run in the eighth.",
            paragraphs=[
                "Aaron Judge's RBI single in the eighth gave the Yankees a 5-3 lead they would not relinquish.",
                "Gerrit Cole pitched seven strong innings, allowing three runs on seven hits.",
            ],
            story_type=StoryType.game_recap,
            teams=["NYY", "BOS"],
            winning_pitcher=_pitcher(4320, "Gerrit Cole", 13, 3, 2.41),
            losing_pitcher=_pitcher(5100, "Chris Sale", 8, 6, 3.22),
            tags=["walk-off"],
        ),
        GameRecap(
            game_id=748294,
            final_score="MIL 4, CHC 2",
            headline="Brewers Edge Cubs in Battle of Wisconsin Rivals",
            deck="Milwaukee's bullpen holds on for a hard-fought victory.",
            paragraphs=[
                "The Milwaukee Brewers held on to beat the Chicago Cubs 4-2 at American Family Field."
            ],
            story_type=StoryType.game_recap,
            teams=["MIL", "CHC"],
        ),
        GameRecap(
            game_id=748295,
            final_score="ATL 6, PHI 5",
            headline="Braves Rally Late to Beat Phillies",
            deck="Atlanta scores three in the seventh to overcome a two-run deficit.",
            paragraphs=[
                "The Atlanta Braves rallied for three runs in the seventh to beat Philadelphia 6-5."
            ],
            story_type=StoryType.game_recap,
            teams=["ATL", "PHI"],
        ),
    ]

    around_the_league = [
        Story(
            headline="Wild Card Race Tightens in the NL",
            deck="Three teams within one game of the final wild card spot.",
            byline="SportzBallz Staff",
            paragraphs=[
                "The National League wild card race is as tight as ever heading into mid-July."
            ],
            story_type=StoryType.wild_card_watch,
        ),
    ]

    transactions = [
        _make_transaction(
            "txn-001",
            "NYY",
            "New York Yankees",
            "Clay Holmes",
            6650,
            TransactionType.placed_on_il,
            "Placed on 15-day IL with right shoulder inflammation.",
        ),
        _make_transaction(
            "txn-002",
            "LAD",
            "Los Angeles Dodgers",
            "Miguel Vargas",
            7700,
            TransactionType.recalled,
            "Recalled from Triple-A Oklahoma City.",
        ),
    ]

    injuries = [
        _make_injury(
            6650, "Clay Holmes", "NYY", "right shoulder inflammation", RosterStatus.fifteen_day_il
        ),
    ]

    historical_items = [
        HistoricalItem(
            year=1941,
            headline="DiMaggio Extends Hitting Streak to 56 Games",
            description="Joe DiMaggio hit safely in his 56th consecutive game on this date in 1941, setting a record that still stands.",
            teams=["NYY"],
            players=["Joe DiMaggio"],
            source="Baseball Reference",
            verified=True,
        ),
    ]

    return Edition(
        edition=_metadata(date_str, "morning", f"{date_str}-0600"),
        lead_story=lead_story,
        secondary_stories=secondary_stories,
        games=games,
        standings=_make_standings(),
        league_leaders=_make_league_leaders(),
        game_recaps=game_recaps,
        around_the_league=around_the_league,
        transactions=transactions,
        injuries=injuries,
        historical_items=historical_items,
        team_game_leaders=[
            TeamGameLeaders(
                game_id=748293,
                away_abbr="BOS",
                home_abbr="NYY",
                performers=[
                    TeamPerformer(
                        player_name="Aaron Judge",
                        player_id=7890,
                        team_abbr="NYY",
                        stat_line="2-for-4, 1 HR, 2 RBI",
                        role="batter",
                        game_id=748293,
                    ),
                    TeamPerformer(
                        player_name="Juan Soto",
                        player_id=6480,
                        team_abbr="NYY",
                        stat_line="2-for-4, 2 R, 1 RBI",
                        role="batter",
                        game_id=748293,
                    ),
                    TeamPerformer(
                        player_name="Gerrit Cole",
                        player_id=4320,
                        team_abbr="NYY",
                        stat_line="7 IP, 2 ER, 9 K",
                        role="pitcher",
                        game_id=748293,
                    ),
                ],
            ),
            TeamGameLeaders(
                game_id=748295,
                away_abbr="ATL",
                home_abbr="PHI",
                performers=[
                    TeamPerformer(
                        player_name="Matt Olson",
                        player_id=5550,
                        team_abbr="ATL",
                        stat_line="2-for-4, 1 HR, 3 RBI",
                        role="batter",
                        game_id=748295,
                    ),
                    TeamPerformer(
                        player_name="Bryce Harper",
                        player_id=7450,
                        team_abbr="PHI",
                        stat_line="3-for-4, 2 RBI",
                        role="batter",
                        game_id=748295,
                    ),
                    TeamPerformer(
                        player_name="Spencer Strider",
                        player_id=4810,
                        team_abbr="ATL",
                        stat_line="6 IP, 2 ER, 10 K",
                        role="pitcher",
                        game_id=748295,
                    ),
                ],
            ),
            TeamGameLeaders(
                game_id=748297,
                away_abbr="HOU",
                home_abbr="TEX",
                performers=[
                    TeamPerformer(
                        player_name="Yordan Alvarez",
                        player_id=6480,
                        team_abbr="HOU",
                        stat_line="2-for-4, 1 HR, 3 RBI",
                        role="batter",
                        game_id=748297,
                    ),
                    TeamPerformer(
                        player_name="José Altuve",
                        player_id=9030,
                        team_abbr="HOU",
                        stat_line="3-for-4, 2 R, 2 RBI",
                        role="batter",
                        game_id=748297,
                    ),
                    TeamPerformer(
                        player_name="Framber Valdez",
                        player_id=5760,
                        team_abbr="HOU",
                        stat_line="7 IP, 4 ER, 7 K",
                        role="pitcher",
                        game_id=748297,
                    ),
                    TeamPerformer(
                        player_name="Corey Seager",
                        player_id=7220,
                        team_abbr="TEX",
                        stat_line="2-for-4, 1 RBI",
                        role="batter",
                        game_id=748297,
                    ),
                ],
            ),
        ],
        generation_metadata=GenerationMetadata(pipeline_version="0.1.0"),
    )


def build_partial_slate_edition(date_str: str = "2026-07-13") -> Edition:
    """5 games, morning edition with mostly scheduled games."""
    games = [
        _make_game_final(
            748400, "BOS", "Boston Red Sox", 111, 2, "NYY", "New York Yankees", 147, 4
        ),
        _make_game_scheduled(748401, "CHC", "Chicago Cubs", 112, "MIL", "Milwaukee Brewers", 158),
        _make_game_scheduled(
            748402, "LAD", "Los Angeles Dodgers", 119, "SF", "San Francisco Giants", 137
        ),
        _make_game_scheduled(748403, "HOU", "Houston Astros", 117, "TEX", "Texas Rangers", 140),
        _make_game_scheduled(
            748404, "ATL", "Atlanta Braves", 144, "PHI", "Philadelphia Phillies", 143
        ),
    ]

    lead_story = Story(
        headline="Morning Slate: Five Games on Tap for Monday",
        deck="A light schedule features key division matchups.",
        byline="SportzBallz Staff",
        paragraphs=[
            "Monday's schedule features five games including a key AL East clash in the Bronx."
        ],
        story_type=StoryType.lead,
        teams=["NYY", "BOS"],
    )

    return Edition(
        edition=_metadata(date_str, "morning", f"{date_str}-0600"),
        lead_story=lead_story,
        games=games,
        generation_metadata=GenerationMetadata(pipeline_version="0.1.0"),
    )


def build_postponement_edition(date_str: str = "2026-07-13") -> Edition:
    """3 games postponed due to rain, 2 final."""

    def _postponed(
        game_id: int,
        away_abbr: str,
        away_name: str,
        away_id: int,
        home_abbr: str,
        home_name: str,
        home_id: int,
    ) -> Game:
        return Game(
            game_id=game_id,
            game_date=date_str,
            status=GameStatus.postponed,
            home=_team(home_id, home_abbr, home_name),
            away=_team(away_id, away_abbr, away_name),
            postponement_reason="Rain",
            venue_name="PNC Park",
            venue_city="Pittsburgh",
        )

    games = [
        _postponed(748500, "NYM", "New York Mets", 121, "PHI", "Philadelphia Phillies", 143),
        _postponed(748501, "ATL", "Atlanta Braves", 144, "WSH", "Washington Nationals", 120),
        _postponed(748502, "BOS", "Boston Red Sox", 111, "BAL", "Baltimore Orioles", 110),
        _make_game_final(
            748503, "LAD", "Los Angeles Dodgers", 119, 3, "SD", "San Diego Padres", 135, 1
        ),
        _make_game_final(748504, "HOU", "Houston Astros", 117, 5, "TEX", "Texas Rangers", 140, 2),
    ]

    lead_story = Story(
        headline="Rain Washes Out Three East Coast Games",
        deck="Heavy storms postpone Phillies, Nationals, and Orioles home games.",
        byline="SportzBallz Staff",
        paragraphs=[
            "Three games were postponed Monday due to heavy rain affecting the Eastern Seaboard.",
            "The Phillies-Mets game at Citizens Bank Park was called off before first pitch.",
        ],
        story_type=StoryType.lead,
        teams=["PHI", "NYM", "WSH", "ATL", "BAL", "BOS"],
    )

    return Edition(
        edition=_metadata(date_str, "evening", f"{date_str}-1800"),
        lead_story=lead_story,
        games=games,
        generation_metadata=GenerationMetadata(pipeline_version="0.1.0"),
    )


def build_doubleheader_edition(date_str: str = "2026-07-13") -> Edition:
    """One team playing 2 games the same day."""
    game1 = Game(
        game_id=748600,
        game_date=date_str,
        status=GameStatus.final,
        home=_team(147, "NYY", "New York Yankees", 4),
        away=_team(111, "BOS", "Boston Red Sox", 2),
        linescore=[
            LinescoreInning(inning=i, away_runs=0, home_runs=1 if i == 3 else 0)
            for i in range(1, 8)
        ],
        is_doubleheader=True,
        doubleheader_game_num=1,
        winning_pitcher=_pitcher(4320, "Gerrit Cole", 13, 3, 2.41),
        losing_pitcher=_pitcher(5100, "Chris Sale", 8, 6, 3.22),
        venue_name="Yankee Stadium",
        venue_city="Bronx",
        time_of_game="2:41",
        tags=["doubleheader"],
    )
    game2 = Game(
        game_id=748601,
        game_date=date_str,
        status=GameStatus.final,
        home=_team(147, "NYY", "New York Yankees", 6),
        away=_team(111, "BOS", "Boston Red Sox", 3),
        linescore=[
            LinescoreInning(inning=i, away_runs=1 if i == 2 else 0, home_runs=2 if i == 5 else 0)
            for i in range(1, 8)
        ],
        is_doubleheader=True,
        doubleheader_game_num=2,
        winning_pitcher=_pitcher(5200, "Luis Severino", 9, 5, 3.10),
        losing_pitcher=_pitcher(5300, "Brayan Bello", 7, 7, 3.85),
        venue_name="Yankee Stadium",
        venue_city="Bronx",
        time_of_game="2:55",
        tags=["doubleheader"],
    )

    lead_story = Story(
        headline="Yankees Sweep Red Sox Doubleheader",
        deck="New York wins both games of the twin bill to take a commanding series lead.",
        byline="SportzBallz Staff",
        paragraphs=[
            "The New York Yankees swept a doubleheader from the Boston Red Sox on Monday, winning 4-2 and 6-3.",
            "Cole was dominant in the opener before Severino coasted in the nightcap.",
        ],
        story_type=StoryType.lead,
        teams=["NYY", "BOS"],
        players=["Gerrit Cole", "Luis Severino"],
    )

    game_recaps = [
        GameRecap(
            game_id=748600,
            final_score="NYY 4, BOS 2",
            headline="Cole Shines as Yankees Take Game 1",
            deck="Gerrit Cole earns his 13th win in the opener.",
            paragraphs=[
                "Gerrit Cole pitched brilliantly in Game 1 of the doubleheader, allowing just two runs."
            ],
            story_type=StoryType.game_recap,
            teams=["NYY", "BOS"],
            tags=["doubleheader"],
        ),
        GameRecap(
            game_id=748601,
            final_score="NYY 6, BOS 3",
            headline="Severino Leads Yankees to Doubleheader Sweep",
            deck="New York's offense explodes in the nightcap.",
            paragraphs=[
                "Luis Severino went seven innings in the nightcap as New York completed the sweep."
            ],
            story_type=StoryType.game_recap,
            teams=["NYY", "BOS"],
            tags=["doubleheader"],
        ),
    ]

    return Edition(
        edition=_metadata(date_str, "final", f"{date_str}-2200"),
        lead_story=lead_story,
        games=[game1, game2],
        game_recaps=game_recaps,
        generation_metadata=GenerationMetadata(pipeline_version="0.1.0"),
    )


def build_no_hitter_edition(date_str: str = "2026-07-13") -> Edition:
    """One game with no_hitter tag on lead story and game."""
    no_hitter_game = Game(
        game_id=748700,
        game_date=date_str,
        status=GameStatus.final,
        home=_team(119, "LAD", "Los Angeles Dodgers", 4),
        away=_team(109, "SD", "San Diego Padres", 0),
        linescore=[
            LinescoreInning(inning=i, away_runs=0, home_runs=1 if i == 3 else 0)
            for i in range(1, 10)
        ],
        winning_pitcher=_pitcher(4810, "Spencer Strider", 14, 3, 2.41),
        losing_pitcher=_pitcher(6000, "Dylan Cease", 9, 7, 3.55),
        venue_name="Dodger Stadium",
        venue_city="Los Angeles",
        attendance=52_312,
        time_of_game="2:28",
        tags=["no-hitter", "shutout"],
    )

    lead_story = Story(
        headline="Strider Throws No-Hitter Against Padres",
        deck="Los Angeles ace fans 14 batters and doesn't allow a hit in historic complete game.",
        byline="SportzBallz Staff",
        paragraphs=[
            "Spencer Strider threw a no-hitter against the San Diego Padres on Monday night at Dodger Stadium, striking out 14 batters in a 4-0 victory.",
            "Strider retired the final 18 batters in a row, sending the Dodger Stadium crowd into a frenzy.",
            "It was the first no-hitter in the major leagues this season.",
        ],
        story_type=StoryType.lead,
        teams=["LAD", "SD"],
        players=["Spencer Strider"],
        facts_used=["game:748700", "player:4810"],
        source_data_references=["game:748700"],
    )

    game_recap = GameRecap(
        game_id=748700,
        final_score="LAD 4, SD 0",
        headline="Strider's No-No: A Historic Night in Los Angeles",
        deck="Spencer Strider fans 14 and allows zero hits in complete game masterpiece.",
        paragraphs=[
            "Spencer Strider was untouchable Monday, throwing a no-hitter and striking out 14 in the Dodgers' 4-0 win over San Diego.",
        ],
        story_type=StoryType.game_recap,
        teams=["LAD", "SD"],
        players=["Spencer Strider"],
        winning_pitcher=_pitcher(4810, "Spencer Strider", 14, 3, 2.41),
        losing_pitcher=_pitcher(6000, "Dylan Cease", 9, 7, 3.55),
        tags=["no-hitter", "shutout"],
    )

    return Edition(
        edition=_metadata(date_str, "final", f"{date_str}-2300"),
        lead_story=lead_story,
        games=[no_hitter_game],
        game_recaps=[game_recap],
        generation_metadata=GenerationMetadata(pipeline_version="0.1.0"),
    )

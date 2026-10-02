from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from src.football.generator import FootballEditionGenerator
from src.markets import Market
from src.models.edition import Edition
from src.models.game import Game
from src.models.story import GameRecap, Story, StoryType


def _story_from_recap(recap: GameRecap) -> Story:
    return Story(
        headline=recap.headline,
        deck=recap.deck,
        byline=recap.byline,
        paragraphs=recap.paragraphs,
        source_data_references=recap.source_data_references,
        story_type=StoryType.lead,
        teams=recap.teams,
        players=recap.players,
        facts_used=recap.facts_used,
        ai_generated=recap.ai_generated,
        source_name=recap.source_name,
        source_url=recap.source_url,
    )


def eliminated_postseason_teams(edition: Edition) -> set[str]:
    eliminated: set[str] = set()
    if not edition.postseason:
        return eliminated
    for series in edition.postseason.series:
        if max(series.away_wins, series.home_wins) < series.wins_required:
            continue
        eliminated.add(
            series.home_team if series.away_wins > series.home_wins else series.away_team
        )
    return eliminated


def baseball_headline_game(edition: Edition, market: Market) -> Game | None:
    postseason_games = edition.postseason.games if edition.postseason else []
    games_by_id = {
        game.game_id: game for game in [*edition.games, *postseason_games]
    }
    recap_games = [
        (recap, games_by_id.get(recap.game_id))
        for recap in edition.game_recaps
        if games_by_id.get(recap.game_id) is not None
    ]

    if edition.postseason and edition.postseason.series:
        postseason_teams = {
            team
            for series in edition.postseason.series
            for team in (series.away_team, series.home_team)
        }
        eliminated_teams = eliminated_postseason_teams(edition)

        try:
            results_date = (
                date.fromisoformat(edition.edition.date) - timedelta(days=1)
            ).isoformat()
        except ValueError:
            results_date = edition.edition.date
        current_postseason_games = [
            game
            for game in games_by_id.values()
            if game.status.value == "final"
            and game.game_date == results_date
            and game.game_type in {"F", "D", "L", "W"}
        ]
        current_market_game = next(
            (
                game
                for team in market.baseball_teams
                if team in postseason_teams
                for game in current_postseason_games
                if team in {game.away.team_abbr, game.home.team_abbr}
            ),
            None,
        )
        if current_market_game is not None:
            return current_market_game
        recap = None
        if recap is None:
            eliminated_market_teams = eliminated_teams.intersection(market.baseball_teams)
            selected_game = next(
                (
                    game
                    for game in current_postseason_games
                    if not eliminated_market_teams.intersection(
                        {game.away.team_abbr, game.home.team_abbr}
                    )
                ),
                None,
            )
            if selected_game is None and eliminated_market_teams:
                selected_game = next(
                    (
                        game
                        for game in sorted(
                            games_by_id.values(),
                            key=lambda candidate: (candidate.game_date, candidate.game_id),
                            reverse=True,
                        )
                        if game.status.value == "final"
                        and game.game_type in {"F", "D", "L", "W"}
                        and not eliminated_market_teams.intersection(
                            {game.away.team_abbr, game.home.team_abbr}
                        )
                    ),
                    None,
                )
            if selected_game is not None:
                return selected_game
    else:
        recap = next(
            (
                recap
                for team in market.baseball_teams
                for recap, _game in recap_games
                if team in recap.teams
            ),
            None,
        )
    if not recap:
        return None
    return games_by_id.get(recap.game_id)


def previous_baseball_lead(
    path: Path | None, *, excluded_teams: set[str] | None = None
) -> Story | None:
    """Return the last published, self-contained market lead for an MLB off-day."""
    if path is None or not path.exists():
        return None
    try:
        previous = Edition.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    lead = previous.lead_story
    if lead is None or not lead.headline.strip() or not lead.paragraphs:
        return None
    if (excluded_teams or set()).intersection(lead.teams):
        return None
    return lead.model_copy(deep=True)


def marketize_baseball(
    edition: Edition,
    market: Market,
    lead_recap: GameRecap | None = None,
    previous_lead: Story | None = None,
) -> Edition:
    localized = edition.model_copy(deep=True)
    localized.edition.market_slug = market.slug
    localized.edition.market_label = market.label
    localized.edition.market_teams = list(market.baseball_teams)
    selected_game = baseball_headline_game(localized, market)
    local_recap = lead_recap or next(
        (
            recap
            for recap in localized.game_recaps
            if selected_game and recap.game_id == selected_game.game_id
        ),
        None,
    )
    if local_recap:
        localized.lead_story = _story_from_recap(local_recap)
    elif previous_lead:
        localized.lead_story = previous_lead.model_copy(deep=True)
    return localized


def football_headline_game(page: dict[str, Any], market: Market) -> dict[str, Any] | None:
    return next(
        (
            game
            for team in market.football_teams
            for game in page.get("scoreboard", [])
            if game.get("completed")
            and team
            in {
                game.get("away", {}).get("abbr"),
                game.get("home", {}).get("abbr"),
            }
        ),
        None,
    )


def marketize_football(
    page: dict[str, Any],
    market: Market,
    lead: dict[str, Any] | None = None,
    *,
    allow_deterministic_lead: bool = True,
) -> dict[str, Any]:
    localized = deepcopy(page)
    localized["market_slug"] = market.slug
    localized["market_label"] = market.label
    localized["market_teams"] = list(market.football_teams)
    localized["canonical_path"] = f"/editions/{market.slug}/football/"
    local_game = football_headline_game(localized, market)
    if lead:
        localized["lead"] = deepcopy(lead)
    elif local_game:
        localized["lead"] = (
            FootballEditionGenerator._lead_story(local_game, market_label=market.label)
            if allow_deterministic_lead
            else None
        )
    return localized

from __future__ import annotations

from copy import deepcopy
from typing import Any

from src.football.generator import FootballEditionGenerator
from src.markets import Market
from src.models.edition import Edition
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


def marketize_baseball(edition: Edition, market: Market) -> Edition:
    localized = edition.model_copy(deep=True)
    localized.edition.market_slug = market.slug
    localized.edition.market_label = market.label
    localized.edition.market_teams = list(market.baseball_teams)
    local_recap = next(
        (
            recap
            for team in market.baseball_teams
            for recap in localized.game_recaps
            if team in recap.teams
        ),
        None,
    )
    if local_recap:
        localized.lead_story = _story_from_recap(local_recap)
    return localized


def marketize_football(page: dict[str, Any], market: Market) -> dict[str, Any]:
    localized = deepcopy(page)
    localized["market_slug"] = market.slug
    localized["market_label"] = market.label
    localized["market_teams"] = list(market.football_teams)
    localized["canonical_path"] = f"/editions/{market.slug}/football/"
    local_game = next(
        (
            game
            for team in market.football_teams
            for game in localized.get("scoreboard", [])
            if game.get("completed")
            and team
            in {
                game.get("away", {}).get("abbr"),
                game.get("home", {}).get("abbr"),
            }
        ),
        None,
    )
    if local_game:
        localized["lead"] = FootballEditionGenerator._lead_story(
            local_game, market_label=market.label
        )
    return localized

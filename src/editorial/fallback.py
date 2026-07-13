# src/editorial/fallback.py
from __future__ import annotations
from jinja2 import Environment, BaseLoader
from src.models.game import Game
from src.models.story import GameRecap, StoryType

RECAP_TEMPLATE = """\
{%- set home_runs = game.home.runs or 0 -%}
{%- set away_runs = game.away.runs or 0 -%}
{%- if home_runs > away_runs -%}
  {%- set winner = game.home -%}
  {%- set loser = game.away -%}
{%- else -%}
  {%- set winner = game.away -%}
  {%- set loser = game.home -%}
{%- endif -%}
The {{ winner.team_name }} defeated the {{ loser.team_name }} {{ winner.runs }}–{{ loser.runs }}\
{% if "walk-off" in game.tags %} in walk-off fashion{% endif %}\
{% if "extra-inning" in game.tags %} in extra innings{% endif %}.\
{% if game.winning_pitcher %} {{ game.winning_pitcher.name }} earned the win.{% endif %}\
{% if game.save_pitcher %} {{ game.save_pitcher.name }} recorded the save.{% endif %}"""

AROUND_THE_LEAGUE_TEMPLATE = """\
{{ item_type }}: {{ description }}"""

_env = Environment(loader=BaseLoader(), trim_blocks=True, lstrip_blocks=True)


def generate_fallback_recap(game: Game) -> GameRecap:
    """Generate a deterministic recap from game data without AI."""
    home_runs = game.home.runs or 0
    away_runs = game.away.runs or 0
    winner = game.home if home_runs > away_runs else game.away
    loser = game.away if home_runs > away_runs else game.home

    headline = f"{winner.team_name} {winner.runs}, {loser.team_name} {loser.runs}"
    body = _env.from_string(RECAP_TEMPLATE).render(game=game).strip()

    return GameRecap(
        headline=headline,
        deck=f"Final: {winner.team_abbr} {winner.runs}, {loser.team_abbr} {loser.runs}",
        byline="SportzBallz Staff",
        paragraphs=[body],
        source_data_references=[f"game:{game.game_id}"],
        story_type=StoryType.game_recap,
        teams=[game.home.team_abbr, game.away.team_abbr],
        players=[],
        facts_used=[
            f"home_runs:{game.home.runs}",
            f"away_runs:{game.away.runs}",
            f"game_id:{game.game_id}",
        ],
        ai_generated=False,
        game_id=game.game_id,
        final_score=f"{winner.team_abbr} {winner.runs}, {loser.team_abbr} {loser.runs}",
        winning_pitcher=game.winning_pitcher,
        losing_pitcher=game.losing_pitcher,
        save_pitcher=game.save_pitcher,
        tags=list(game.tags),
    )

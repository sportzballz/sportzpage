# tests/unit/test_renderer.py
"""Unit tests for HTMLRenderer and render_from_file."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.models.edition import Edition, EditionMetadata, GenerationMetadata
from src.models.game import BettingLine, Game, GameStatus, TeamGameLine
from src.models.story import Story, StoryType
from src.rendering.html_renderer import HTMLRenderer
from src.rendering.renderer import render_from_file
from tests.fixtures.builders import build_full_slate_edition


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

TEMPLATES_DIR = Path(__file__).parents[2] / "templates"


def make_renderer() -> HTMLRenderer:
    return HTMLRenderer(templates_dir=TEMPLATES_DIR)


def make_minimal_edition(**overrides) -> Edition:
    """Return the smallest valid Edition that still renders successfully."""
    metadata = EditionMetadata(
        id="2026-07-13-0600",
        type="morning",
        date="2026-07-13",
        generated_at=datetime(2026, 7, 13, 6, 0, 0, tzinfo=timezone.utc),
        data_current_through=datetime(2026, 7, 13, 5, 55, 0, tzinfo=timezone.utc),
        timezone="America/New_York",
        status="published",
    )
    kwargs = dict(
        edition=metadata,
        lead_story=None,
        secondary_stories=[],
        games=[],
        standings=None,
        league_leaders=None,
        game_recaps=[],
        around_the_league=[],
        transactions=[],
        injuries=[],
        historical_items=[],
        generation_metadata=GenerationMetadata(pipeline_version="0.1.0"),
    )
    kwargs.update(overrides)
    return Edition(**kwargs)


# ---------------------------------------------------------------------------
# Test 1: Basic render
# ---------------------------------------------------------------------------


def test_basic_render_returns_html():
    edition = make_minimal_edition()
    renderer = make_renderer()
    result = renderer.render(edition)
    assert isinstance(result, str)
    assert len(result) > 0
    assert "<!doctype html>" in result.lower()


def test_standings_have_league_and_division_labels():
    html = make_renderer().render(build_full_slate_edition())

    assert "American League" in html
    assert "National League" in html
    assert "East Division" in html
    assert "Central Division" in html
    assert "West Division" in html


def test_box_scores_follow_standings():
    html = make_renderer().render(build_full_slate_edition())

    assert html.index('id="standings"') < html.index('id="box-scores"')
    assert html.index('id="box-scores"') < html.index('id="league-leaders"')


def test_scoreboard_has_concise_today_schedule():
    html = make_renderer().render(build_full_slate_edition())
    scoreboard = html.split('id="scoreboard"', 1)[1].split("</section>", 1)[0]

    assert "Today's Schedule" in scoreboard
    assert "schedule-summary-table" in scoreboard
    assert "Teams" in scoreboard
    assert "Time" in scoreboard
    assert "Venue" in scoreboard
    assert "Pitcher" not in scoreboard.split("Today's Schedule", 1)[1]


def test_scoreboard_does_not_render_recap_links():
    html = make_renderer().render(build_full_slate_edition())
    scoreboard = html.split('id="scoreboard"', 1)[1].split("</section>", 1)[0]

    assert ">Recap<" not in scoreboard
    assert 'class="recap-cell"' not in scoreboard


def test_history_event_fragments_render_as_one_headline():
    html = make_renderer().render(build_full_slate_edition())
    first_history_item = html.split('class="history-item"', 1)[1].split("</li>", 1)[0]

    assert first_history_item.count('class="history-headline"') == 1
    assert 'class="history-description"' not in first_history_item


# ---------------------------------------------------------------------------
# Test 2: All section IDs present
# ---------------------------------------------------------------------------

EXPECTED_IDS = [
    'id="front-page"',
    'id="scoreboard"',
    'id="todays-games"',
    'id="standings"',
    'id="league-leaders"',
    'id="around-the-league"',
    'id="transactions"',
    'id="history"',
]


@pytest.mark.parametrize("section_id", EXPECTED_IDS)
def test_all_section_ids_present(section_id: str):
    edition = make_minimal_edition()
    renderer = make_renderer()
    html = renderer.render(edition)
    assert section_id in html, f"Missing section anchor: {section_id}"


# ---------------------------------------------------------------------------
# Test 3: Edition ID meta tag
# ---------------------------------------------------------------------------


def test_edition_id_meta_tag():
    edition = make_minimal_edition()
    renderer = make_renderer()
    html = renderer.render(edition)
    assert 'name="daily-sportz-page-edition-id"' in html
    assert "2026-07-13-0600" in html
    assert "Monday, July 13, 2026" in html


def test_production_urls_use_sportzpage_path():
    edition = make_minimal_edition()
    html = make_renderer().render(edition)
    assert 'href="https://thedailysportspage.com/"' in html
    assert 'href="static/css/daily-sports-page.css?v=20260822-blackletter-masthead"' in html
    assert 'src="static/js/daily-sports-page.js"' in html


def test_todays_games_renders_moneylines_and_run_total_only():
    game = Game(
        game_id=123,
        game_date="2026-07-13",
        status=GameStatus.scheduled,
        away=TeamGameLine(team_id=111, team_abbr="BOS", team_name="Boston Red Sox"),
        home=TeamGameLine(team_id=147, team_abbr="NYY", team_name="New York Yankees"),
        betting_line=BettingLine(
            away_moneyline=125,
            home_moneyline=-145,
            run_total=8.5,
            provider="DraftKings",
        ),
    )

    rendered = make_renderer().render(make_minimal_edition(games=[game]))

    assert "BOS</strong> +125" in rendered
    assert "NYY</strong> -145" in rendered
    assert "O/U</strong> 8.5" in rendered
    assert "Run Line" not in rendered
    assert "Over Odds" not in rendered


# ---------------------------------------------------------------------------
# Test 4: Masthead has generated_at and data_current_through separately
# ---------------------------------------------------------------------------


def test_masthead_timestamps():
    edition = make_minimal_edition()
    renderer = make_renderer()
    html = renderer.render(edition)
    # generated_at: 6:00 AM UTC
    assert "Generated at" in html
    # data_current_through: 5:55 AM UTC
    assert "Data current through" in html
    # The two times should appear in the masthead and be distinct
    assert "06:00" in html or "06:00" in html or "AM" in html


# ---------------------------------------------------------------------------
# Test 5: HTML escaping — XSS injection in team name
# ---------------------------------------------------------------------------


def test_html_escaping_team_name():
    xss_name = "<script>alert(1)</script>"
    away = TeamGameLine(
        team_id=1,
        team_abbr="XSS",
        team_name=xss_name,
        runs=None,
        hits=None,
        errors=None,
    )
    home = TeamGameLine(
        team_id=2,
        team_abbr="HOM",
        team_name="Home Team",
        runs=None,
        hits=None,
        errors=None,
    )
    game = Game(
        game_id=999,
        game_date="2026-07-13",
        status=GameStatus.scheduled,
        home=home,
        away=away,
    )
    edition = make_minimal_edition(games=[game])
    renderer = make_renderer()
    html = renderer.render(edition)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html or "alert" not in html


# ---------------------------------------------------------------------------
# Test 6: Deterministic output
# ---------------------------------------------------------------------------


def test_render_is_deterministic():
    edition = make_minimal_edition()
    renderer = make_renderer()
    html1 = renderer.render(edition)
    html2 = renderer.render(edition)
    assert html1 == html2


# ---------------------------------------------------------------------------
# Test 7: Null sections render without exception
# ---------------------------------------------------------------------------


def test_null_sections_render_ok():
    edition = make_minimal_edition(
        standings=None,
        lead_story=None,
        league_leaders=None,
    )
    renderer = make_renderer()
    # Should not raise
    html = renderer.render(edition)
    assert "<!doctype html>" in html.lower()


# ---------------------------------------------------------------------------
# Test 8: render_from_file writes index.html and edition.json
# ---------------------------------------------------------------------------


def test_render_from_file(tmp_path: Path):
    edition = make_minimal_edition()
    edition_json = tmp_path / "edition.json"
    edition_json.write_text(edition.model_dump_json(), encoding="utf-8")

    output_dir = tmp_path / "output"
    result = render_from_file(edition_json, output_dir)

    assert result == output_dir / "index.html"
    assert (output_dir / "index.html").exists()
    assert (output_dir / "edition.json").exists()

    html = (output_dir / "index.html").read_text(encoding="utf-8")
    assert "<!doctype html>" in html.lower()

    reloaded = json.loads((output_dir / "edition.json").read_text())
    assert reloaded["edition"]["id"] == "2026-07-13-0600"


# ---------------------------------------------------------------------------
# Test: Lead story renders when present
# ---------------------------------------------------------------------------


def test_lead_story_renders():
    story = Story(
        headline="Yankees Win World Series",
        deck="New York defeats the Dodgers in Game 7.",
        byline="SportzBallz Staff",
        paragraphs=["It was a tense night at Yankee Stadium."],
        story_type=StoryType.lead,
    )
    edition = make_minimal_edition(lead_story=story)
    renderer = make_renderer()
    html = renderer.render(edition)
    assert "Yankees Win World Series" in html
    assert "Daily Sports Page Staff" in html
    assert "daily-sports-page.css?v=20260822-blackletter-masthead" in html

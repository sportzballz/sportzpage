# tests/integration/test_data_accuracy.py
"""Data accuracy tests: verify edition data appears faithfully in rendered HTML."""

from __future__ import annotations

import html.parser
from pathlib import Path

from tests.fixtures.builders import build_full_slate_edition
from src.models.edition import Edition
from src.rendering.html_renderer import HTMLRenderer

TEMPLATES_DIR = Path(__file__).parents[2] / "templates"


class _TextCollector(html.parser.HTMLParser):
    """Collect all text content and tag attributes from an HTML document."""

    def __init__(self) -> None:
        super().__init__()
        self.text_chunks: list[str] = []
        self.attrs_seen: list[dict[str, str | None]] = []

    def handle_data(self, data: str) -> None:
        self.text_chunks.append(data)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.attrs_seen.append(dict(attrs))

    @property
    def full_text(self) -> str:
        return " ".join(self.text_chunks)


def _render_full_slate() -> tuple[str, Edition]:
    edition = build_full_slate_edition()
    renderer = HTMLRenderer(templates_dir=TEMPLATES_DIR)
    html = renderer.render(edition)
    return html, edition


def test_edition_id_in_html():
    """The edition's ID must appear in the rendered HTML."""
    html_content, edition = _render_full_slate()
    assert edition.edition.id in html_content, (
        f"Edition ID {edition.edition.id!r} not found in HTML"
    )


def test_team_abbreviation_in_html():
    """At least one team abbreviation from a game appears in the HTML."""
    html_content, edition = _render_full_slate()
    abbrs = {g.home.team_abbr for g in edition.games} | {g.away.team_abbr for g in edition.games}
    found = [a for a in abbrs if a in html_content]
    assert found, f"No team abbreviations from games found in HTML. Tried: {abbrs}"


def test_edition_type_in_html():
    """The edition type (e.g. 'morning') appears somewhere in the rendered HTML."""
    html_content, edition = _render_full_slate()
    edition_type = edition.edition.type
    assert edition_type in html_content.lower(), f"Edition type {edition_type!r} not found in HTML"


def test_lead_story_headline_in_html():
    """The lead story headline must appear in the HTML."""
    html_content, edition = _render_full_slate()
    assert edition.lead_story is not None, "Expected a lead story in the full-slate edition"
    headline = edition.lead_story.headline
    assert headline in html_content, f"Lead story headline {headline!r} not found in HTML"

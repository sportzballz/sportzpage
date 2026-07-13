# tests/unit/test_accessibility.py
"""Accessibility smoke tests using stdlib html.parser only."""

from __future__ import annotations

import html.parser
from pathlib import Path

from tests.fixtures.builders import build_full_slate_edition
from src.rendering.html_renderer import HTMLRenderer

TEMPLATES_DIR = Path(__file__).parents[2] / "templates"


class _AccessibilityParser(html.parser.HTMLParser):
    """Parse HTML and collect accessibility-relevant elements."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []
        self._in_title = False
        self.title_text: str = ""
        self._text_buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_dict = dict(attrs)
        self.tags.append((tag.lower(), attr_dict))
        if tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_text += data

    # -- convenience helpers --

    def find_tags(self, name: str) -> list[dict[str, str | None]]:
        return [attrs for tag, attrs in self.tags if tag == name]

    def find_tag_with_attr(
        self, name: str, attr: str, value: str | None = None
    ) -> list[dict[str, str | None]]:
        results = []
        for tag, attrs in self.tags:
            if tag == name:
                if attr in attrs:
                    if value is None or attrs[attr] == value:
                        results.append(attrs)
        return results

    def html_attrs(self) -> dict[str, str | None]:
        for tag, attrs in self.tags:
            if tag == "html":
                return attrs
        return {}


def _parse(html_content: str) -> _AccessibilityParser:
    parser = _AccessibilityParser()
    parser.feed(html_content)
    return parser


def _render() -> str:
    edition = build_full_slate_edition()
    renderer = HTMLRenderer(templates_dir=TEMPLATES_DIR)
    return renderer.render(edition)


# Module-level render so we only render once for all tests in this module
_HTML = None


def _get_html() -> str:
    global _HTML
    if _HTML is None:
        _HTML = _render()
    return _HTML


def test_skip_to_content_link_exists():
    """A skip-to-content anchor link must be present (by class or visible text)."""
    html_content = _get_html()
    has_skip_class = "skip-link" in html_content
    has_skip_text = "skip to content" in html_content.lower()
    assert has_skip_class or has_skip_text, (
        "No skip-to-content link found (expected class='skip-link' or 'Skip to content' text)"
    )


def test_main_element_exists():
    """At least one <main> element must be present."""
    parser = _parse(_get_html())
    mains = parser.find_tags("main")
    assert mains, "No <main> element found in rendered HTML"


def test_title_tag_present():
    """The page must have a <title> tag with non-empty content."""
    parser = _parse(_get_html())
    titles = parser.find_tags("title")
    assert titles, "No <title> tag found"
    assert parser.title_text.strip(), "Title tag is empty"


def test_html_lang_attribute():
    """The <html> element must have a lang attribute."""
    parser = _parse(_get_html())
    html_attrs = parser.html_attrs()
    assert "lang" in html_attrs, "<html> element is missing the lang attribute"
    assert html_attrs["lang"], "lang attribute on <html> is empty"


def test_img_tags_have_alt():
    """Every <img> tag must have an alt attribute (may be empty string for decorative images)."""
    parser = _parse(_get_html())
    imgs = parser.find_tags("img")
    missing_alt = [attrs for attrs in imgs if "alt" not in attrs]
    assert not missing_alt, (
        f"{len(missing_alt)} <img> tag(s) are missing alt attributes: {missing_alt}"
    )


def test_league_leaders_has_aria():
    """The league-leaders section must use ARIA tab pattern (role=tablist or aria-label on controls)."""
    html_content = _get_html()
    has_tablist = 'role="tablist"' in html_content
    has_aria_label_on_tabs = "aria-label=" in html_content and "league-leaders" in html_content
    has_aria_controls = "aria-controls=" in html_content
    assert has_tablist or has_aria_label_on_tabs or has_aria_controls, (
        "League-leaders section is missing ARIA tab pattern "
        "(expected role='tablist', aria-label, or aria-controls)"
    )

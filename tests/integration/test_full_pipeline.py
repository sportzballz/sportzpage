# tests/integration/test_full_pipeline.py
"""Integration test: full fixture → validate → render pipeline."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from tests.fixtures.builders import build_full_slate_edition
from src.validation.validator import ContentValidator
from src.rendering.html_renderer import HTMLRenderer

TEMPLATES_DIR = Path(__file__).parents[2] / "templates"

REQUIRED_SECTION_IDS = [
    'id="front-page"',
    'id="scoreboard"',
    'id="todays-games"',
    'id="standings"',
    'id="league-leaders"',
    'id="transactions"',
    'id="history"',
]


def test_full_slate_pipeline():
    """Build → validate → render → verify outputs."""
    edition = build_full_slate_edition()

    # Validate
    validator = ContentValidator()
    report = validator.validate_edition(edition)
    assert not report.has_errors, f"Validation errors: {report.errors}"

    # Render to HTML
    renderer = HTMLRenderer(templates_dir=TEMPLATES_DIR)
    html = renderer.render(edition)
    assert isinstance(html, str) and len(html) > 0, "render() returned empty output"

    # Write to temp dir
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp)
        index = out / "index.html"
        index.write_text(html, encoding="utf-8")
        edition_json_path = out / "edition.json"
        edition_json_path.write_text(edition.model_dump_json(), encoding="utf-8")

        assert index.exists(), "index.html not written"
        assert edition_json_path.exists(), "edition.json not written"

        html_bytes = index.read_bytes()
        assert len(html_bytes) < 2 * 1024 * 1024, f"HTML exceeds 2 MB: {len(html_bytes)} bytes"

        html_content = index.read_text(encoding="utf-8")

        # All required section IDs present
        for section_id in REQUIRED_SECTION_IDS:
            assert section_id in html_content, f"Missing section: {section_id}"
        assert 'id="around-the-league"' not in html_content
        assert "Around the League" not in html_content

        # Edition ID meta tag present
        edition_id = edition.edition.id
        assert edition_id in html_content, f"Edition ID {edition_id!r} not found in HTML"
        assert 'name="daily-sportz-page-edition-id"' in html_content, "Edition ID meta tag missing"

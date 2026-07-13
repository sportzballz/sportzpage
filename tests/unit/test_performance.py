# tests/unit/test_performance.py
"""HTML size performance checks."""

from __future__ import annotations

from pathlib import Path

from tests.fixtures.builders import build_full_slate_edition
from src.rendering.html_renderer import HTMLRenderer

TEMPLATES_DIR = Path(__file__).parents[2] / "templates"

MAX_BYTES = 500 * 1024  # 500 KB


def test_full_slate_html_under_500kb():
    """Rendered full-slate edition HTML must be under 500 KB."""
    edition = build_full_slate_edition()
    renderer = HTMLRenderer(templates_dir=TEMPLATES_DIR)
    html = renderer.render(edition)
    size_bytes = len(html.encode("utf-8"))
    # Print size for visibility
    print(f"\n[test_performance] HTML size: {size_bytes:,} bytes ({size_bytes / 1024:.1f} KB)")
    assert size_bytes < MAX_BYTES, (
        f"HTML size {size_bytes:,} bytes exceeds limit of {MAX_BYTES:,} bytes ({MAX_BYTES // 1024} KB)"
    )

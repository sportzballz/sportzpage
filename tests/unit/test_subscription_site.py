from __future__ import annotations

import json
import re
from datetime import date, timedelta
from pathlib import Path

from scripts.assemble_subscription_site import ARCHIVE_LIMIT, assemble


def _write_edition(directory: Path, day: str, marker: str = "full-story-marker") -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payload = {
        "edition": {"id": f"{day}-morning", "date": day},
        "lead_story": {
            "headline": f"Headline for {day}",
            "deck": "A concise public preview.",
            "paragraphs": [marker],
        },
    }
    (directory / "edition.json").write_text(json.dumps(payload), encoding="utf-8")
    (directory / "index.html").write_text(
        f'<html><head><link rel="canonical" href="https://thedailysportspage.com/"></head>'
        f"<body>{marker}</body></html>",
        encoding="utf-8",
    )


def test_assembles_honor_supported_homepage_current_and_delivery(tmp_path: Path) -> None:
    build = tmp_path / "build"
    football = tmp_path / "football"
    static = tmp_path / "static"
    _write_edition(build, "2026-08-21")
    _write_edition(football, "2026-08-21", "football-full-marker")
    (static / "css").mkdir(parents=True)
    (static / "css" / "daily-sports-page.css").write_text("body{}", encoding="utf-8")

    output = tmp_path / "dist"
    assemble(build, football, static, tmp_path / "previous", output)

    landing = (output / "index.html").read_text(encoding="utf-8")
    assert "Headline for 2026-08-21" in landing
    assert "full-story-marker" not in landing
    assert "open to everyone and supported on the honor system" in landing
    assert "Last Week in Sports" in landing
    assert "Previous seven editions" not in landing
    assert "One-time or monthly tips through Buy Me a Coffee" not in landing
    assert "Buy me a beer 🍻" in landing
    assert "https://buymeacoffee.com/thedailysportspage" in landing
    landing_text = re.sub(r"<[^>]+>", " ", landing).lower()
    assert "free" not in landing_text
    assert "subscribe" not in landing_text
    assert 'subscription.css?v=20260827-standings-contrast' in landing
    assert 'href="/subscriber/current/"' in landing
    assert "full-story-marker" in (output / "subscriber/current/index.html").read_text()
    assert "football-full-marker" in (output / "subscriber/current/football/index.html").read_text()
    assert "Read the complete edition" in (output / "delivery/current/email.html").read_text()
    delivery = json.loads((output / "delivery/current/manifest.json").read_text())
    assert delivery["edition_url"].endswith("/subscriber/current/")
    assert set(delivery["formats"]) == {"digest_html", "full_html", "print_html"}
    assert json.loads((output / "archive/manifest.json").read_text()) == {"editions": []}
    current_html = (output / "subscriber/current/index.html").read_text()
    assert 'rel="canonical" href="https://thedailysportspage.com/subscriber/current/"' in current_html
    assert '"@type":"NewsArticle"' in current_html
    assert current_html.count('property="og:type"') == 1
    assert "Headline for 2026-08-21 — The Daily Sports Page" in current_html
    assert "Sitemap: https://thedailysportspage.com/sitemap.xml" in (output / "robots.txt").read_text()
    assert "https://thedailysportspage.com/subscriber/current/" in (output / "sitemap.xml").read_text()


def test_promotes_previous_current_and_keeps_seven_editions(tmp_path: Path) -> None:
    build = tmp_path / "build"
    football = tmp_path / "football"
    static = tmp_path / "static"
    _write_edition(build, "2026-08-21")
    _write_edition(football, "2026-08-21")
    static.mkdir()

    previous = tmp_path / "previous"
    _write_edition(previous / "subscriber/current", "2026-08-20", "yesterday-full")
    previous_index = previous / "subscriber/current/index.html"
    previous_index.write_text(
        previous_index.read_text().replace(
            "</body>",
            '<ul><li class="support-item">'
            '<a href="https://buymeacoffee.com/thedailysportspage">'
            "Buy me a beer 🍻</a></li></ul></body>",
        )
    )
    for offset in range(2, 10):
        day = (date(2026, 8, 21) - timedelta(days=offset)).isoformat()
        _write_edition(previous / "archive" / day, day)
    _write_edition(previous / "archive/2026-08-21", "2026-08-21", "current-must-stay-paid")

    output = tmp_path / "dist"
    assemble(build, football, static, previous, output)

    manifest = json.loads((output / "archive/manifest.json").read_text())["editions"]
    assert len(manifest) == ARCHIVE_LIMIT
    assert manifest[0] == "2026-08-20"
    assert manifest[-1] == "2026-08-14"
    assert "yesterday-full" in (output / "archive/2026-08-20/index.html").read_text()
    assert not (output / "archive/2026-08-13").exists()
    assert not (output / "archive/2026-08-21").exists()
    assert "/archive/2026-08-20/" in (output / "index.html").read_text()
    archived_html = (output / "archive/2026-08-20/index.html").read_text()
    assert "buymeacoffee.com" not in archived_html
    assert "Buy me a beer" not in archived_html
    assert 'rel="canonical" href="https://thedailysportspage.com/archive/2026-08-20/"' in archived_html
    assert 'property="og:type" content="article"' in archived_html
    sitemap = (output / "sitemap.xml").read_text()
    assert "https://thedailysportspage.com/archive/2026-08-20/" in sitemap
    assert "https://thedailysportspage.com/support/" not in sitemap
    assert "https://thedailysportspage.com/subscribe/" not in sitemap


def test_accepts_legacy_dated_archive_without_edition_json(tmp_path: Path) -> None:
    build = tmp_path / "build"
    football = tmp_path / "football"
    static = tmp_path / "static"
    _write_edition(build, "2026-08-21")
    _write_edition(football, "2026-08-21")
    static.mkdir()
    legacy = tmp_path / "previous/archive/2026-08-20"
    legacy.mkdir(parents=True)
    (legacy / "index.html").write_text("legacy newspaper", encoding="utf-8")

    output = tmp_path / "dist"
    assemble(build, football, static, tmp_path / "previous", output)

    assert json.loads((output / "archive/manifest.json").read_text())["editions"] == ["2026-08-20"]
    assert (output / "archive/2026-08-20/index.html").read_text() == "legacy newspaper"


def test_cloudfront_function_routes_football_to_current_edition() -> None:
    code = Path("terraform/functions/directory-index.js").read_text(encoding="utf-8")
    assert "uri === '/football'" in code
    assert "location: { value: '/subscriber/current/football/' }" in code
    assert "uri.startsWith('/subscriber/')" not in code
    assert "uri.startsWith('/delivery/')" not in code
    assert "request.uri = '/static/icons/favicon.ico'" in code


def test_subscription_panels_span_the_newspaper_grid() -> None:
    css = Path("static/css/subscription.css").read_text(encoding="utf-8")
    panel_rule = css.split(".free-archive {", maxsplit=1)[1].split("}", maxsplit=1)[0]
    assert "grid-column: 1 / -1" in panel_rule
    assert "min-width: 0" in panel_rule

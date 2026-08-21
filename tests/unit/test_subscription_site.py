from __future__ import annotations

import json
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
    (directory / "index.html").write_text(f"<html>{marker}</html>", encoding="utf-8")


def test_assembles_teaser_protected_current_and_delivery(tmp_path: Path) -> None:
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
    assert "$2/month" in landing
    assert "full-story-marker" in (output / "subscriber/current/index.html").read_text()
    assert "football-full-marker" in (output / "subscriber/current/football/index.html").read_text()
    assert "Read the complete edition" in (output / "delivery/current/email.html").read_text()
    delivery = json.loads((output / "delivery/current/manifest.json").read_text())
    assert delivery["protected_url"].endswith("/subscriber/current/")
    assert set(delivery["formats"]) == {"digest_html", "full_html", "print_html"}
    assert json.loads((output / "archive/manifest.json").read_text()) == {"editions": []}


def test_promotes_previous_current_and_keeps_seven_free_editions(tmp_path: Path) -> None:
    build = tmp_path / "build"
    football = tmp_path / "football"
    static = tmp_path / "static"
    _write_edition(build, "2026-08-21")
    _write_edition(football, "2026-08-21")
    static.mkdir()

    previous = tmp_path / "previous"
    _write_edition(previous / "subscriber/current", "2026-08-20", "yesterday-full")
    for offset in range(2, 10):
        day = (date(2026, 8, 21) - timedelta(days=offset)).isoformat()
        _write_edition(previous / "archive" / day, day)

    output = tmp_path / "dist"
    assemble(build, football, static, previous, output)

    manifest = json.loads((output / "archive/manifest.json").read_text())["editions"]
    assert len(manifest) == ARCHIVE_LIMIT
    assert manifest[0] == "2026-08-20"
    assert manifest[-1] == "2026-08-14"
    assert "yesterday-full" in (output / "archive/2026-08-20/index.html").read_text()
    assert not (output / "archive/2026-08-13").exists()
    assert "/archive/2026-08-20/" in (output / "index.html").read_text()


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


def test_cloudfront_function_blocks_unauthenticated_current_and_delivery() -> None:
    code = Path("terraform/functions/directory-index.js").read_text(encoding="utf-8")
    assert "uri.startsWith('/subscriber/')" in code
    assert "uri.startsWith('/delivery/')" in code
    assert "location: { value: '/subscribe/' }" in code

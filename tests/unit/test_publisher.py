# tests/unit/test_publisher.py
from __future__ import annotations

from pathlib import Path

import pytest

from src.publishing.publisher import PublicationError, Publisher


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_publisher(tmp_path: Path, cdn_purge_hook: str | None = None) -> Publisher:
    return Publisher(
        publish_root=tmp_path / "www",
        archive_root=tmp_path / "archive",
        last_known_good_path=tmp_path / "www" / "index.html.lkg",
        cdn_purge_hook=cdn_purge_hook,
    )


def _make_build(tmp_path: Path, content: str = "<html>edition</html>") -> Path:
    build = tmp_path / "build"
    build.mkdir(parents=True, exist_ok=True)
    (build / "index.html").write_text(content)
    return build


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_successful_publish(tmp_path: Path) -> None:
    """Published index.html must exist in publish_root after a successful publish."""
    publisher = _make_publisher(tmp_path)
    build = _make_build(tmp_path)

    publisher.publish(build, "2026-07-13-0600")

    assert (tmp_path / "www" / "index.html").exists()


def test_last_known_good_saved_on_second_publish(tmp_path: Path) -> None:
    """LKG must contain the FIRST edition's content after the second publish."""
    publisher = _make_publisher(tmp_path)

    first_build = _make_build(tmp_path / "build1", content="<html>first</html>")
    publisher.publish(first_build, "2026-07-13-0600")

    second_build = _make_build(tmp_path / "build2", content="<html>second</html>")
    publisher.publish(second_build, "2026-07-13-1200")

    lkg = tmp_path / "www" / "index.html.lkg"
    assert lkg.exists()
    assert "first" in lkg.read_text()


def test_missing_build_dir_raises(tmp_path: Path) -> None:
    """Publishing a non-existent build directory must raise PublicationError."""
    publisher = _make_publisher(tmp_path)

    with pytest.raises(PublicationError, match="does not exist"):
        publisher.publish(Path("/nonexistent-build-dir-xyz"), "test-id")


def test_missing_index_html_raises(tmp_path: Path) -> None:
    """Build dir with no index.html must raise PublicationError."""
    publisher = _make_publisher(tmp_path)
    build = tmp_path / "build"
    build.mkdir()
    # No index.html written

    with pytest.raises(PublicationError, match="Required file missing"):
        publisher.publish(build, "test-id")


def test_rollback_restores_lkg(tmp_path: Path) -> None:
    """rollback() must overwrite the live index.html with LKG content."""
    publisher = _make_publisher(tmp_path)

    first_build = _make_build(tmp_path / "build1", content="<html>lkg-content</html>")
    publisher.publish(first_build, "2026-07-13-0600")

    second_build = _make_build(tmp_path / "build2", content="<html>new-content</html>")
    publisher.publish(second_build, "2026-07-13-1200")

    publisher.rollback()

    live = (tmp_path / "www" / "index.html").read_text()
    assert "lkg-content" in live


def test_rollback_with_no_lkg_raises(tmp_path: Path) -> None:
    """rollback() with no LKG file must raise PublicationError."""
    publisher = _make_publisher(tmp_path)

    with pytest.raises(PublicationError, match="No last-known-good"):
        publisher.rollback()


def test_archive_created(tmp_path: Path) -> None:
    """Archive file must exist at archive/{edition_id}.html after publish."""
    publisher = _make_publisher(tmp_path)
    build = _make_build(tmp_path)

    publisher.publish(build, "2026-07-13-0600")

    archive_file = tmp_path / "archive" / "2026-07-13-0600.html"
    assert archive_file.exists()


def test_cdn_purge_hook_skipped_when_none(tmp_path: Path) -> None:
    """Publisher with cdn_purge_hook=None must complete publish without error."""
    publisher = _make_publisher(tmp_path, cdn_purge_hook=None)
    build = _make_build(tmp_path)

    # Should not raise
    publisher.publish(build, "2026-07-13-0600")

    assert (tmp_path / "www" / "index.html").exists()


def test_assets_copied_before_html(tmp_path: Path) -> None:
    """Static assets from the build dir must appear under publish_root/static/."""
    publisher = _make_publisher(tmp_path)
    build = _make_build(tmp_path)

    css_dir = build / "static" / "css"
    css_dir.mkdir(parents=True)
    (css_dir / "main.css").write_text("body { color: red; }")

    publisher.publish(build, "2026-07-13-0600")

    published_css = tmp_path / "www" / "static" / "css" / "main.css"
    assert published_css.exists()
    assert "color: red" in published_css.read_text()

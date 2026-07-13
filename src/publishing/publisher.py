# src/publishing/publisher.py
from __future__ import annotations
import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class PublicationError(Exception):
    """Raised when publication cannot complete safely."""


class Publisher:
    """Atomically publishes a validated build directory to the CDN origin."""

    def __init__(
        self,
        publish_root: Path,
        archive_root: Path,
        last_known_good_path: Path,
        cdn_purge_hook: str | None = None,
    ) -> None:
        self._publish_root = publish_root
        self._archive_root = archive_root
        self._last_known_good = last_known_good_path
        self._cdn_purge_hook = cdn_purge_hook

    def publish(self, build_dir: Path, edition_id: str) -> None:
        """
        Atomically publish the build directory.
        Steps: verify → save LKG → publish assets → atomic HTML rename → verify → CDN purge → archive
        """
        self._verify_build(build_dir)
        self._save_last_known_good()
        self._publish_assets(build_dir)
        self._atomic_publish_html(build_dir)
        self._verify_published()
        self._purge_cdn()
        self._archive(build_dir, edition_id)
        logger.info("edition %s published successfully", edition_id)

    def rollback(self) -> None:
        """Restore the last-known-good edition."""
        if not self._last_known_good.exists():
            raise PublicationError("No last-known-good edition available for rollback.")
        dest = self._publish_root / "index.html"
        shutil.copy2(self._last_known_good, dest)
        logger.warning("rolled back to last-known-good edition")

    def _verify_build(self, build_dir: Path) -> None:
        if not build_dir.exists():
            raise PublicationError(f"Build directory does not exist: {build_dir}")
        required = ["index.html"]
        for f in required:
            if not (build_dir / f).exists():
                raise PublicationError(f"Required file missing from build: {f}")

    def _save_last_known_good(self) -> None:
        live = self._publish_root / "index.html"
        if live.exists():
            self._last_known_good.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(live, self._last_known_good)

    def _publish_assets(self, build_dir: Path) -> None:
        assets_src = build_dir / "static"
        if assets_src.exists():
            dest = self._publish_root / "static"
            shutil.copytree(assets_src, dest, dirs_exist_ok=True)

    def _atomic_publish_html(self, build_dir: Path) -> None:
        self._publish_root.mkdir(parents=True, exist_ok=True)
        src = build_dir / "index.html"
        dest = self._publish_root / "index.html"
        tmp = dest.with_suffix(".html.tmp")
        shutil.copy2(src, tmp)
        tmp.rename(dest)  # atomic on POSIX

    def _verify_published(self) -> None:
        published = self._publish_root / "index.html"
        if not published.exists():
            raise PublicationError("Published index.html not found after rename.")

    def _purge_cdn(self) -> None:
        if not self._cdn_purge_hook:
            return
        try:
            subprocess.run([self._cdn_purge_hook], check=True, timeout=30)
            logger.info("CDN cache purged successfully")
        except Exception as exc:
            logger.warning("CDN purge failed (non-fatal): %s", exc)

    def _archive(self, build_dir: Path, edition_id: str) -> None:
        self._archive_root.mkdir(parents=True, exist_ok=True)
        dest = self._archive_root / f"{edition_id}.html"
        shutil.copy2(build_dir / "index.html", dest)
        logger.info("archived edition to %s", dest)

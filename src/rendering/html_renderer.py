# src/rendering/html_renderer.py
from __future__ import annotations
import json
import logging
import re
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape, StrictUndefined
from src.models.edition import Edition

logger = logging.getLogger(__name__)


class HTMLRenderer:
    """Renders a validated Edition to static HTML using Jinja2."""

    def __init__(
        self, templates_dir: Path, static_asset_manifest: dict[str, str] | None = None
    ) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=select_autoescape(["html", "j2"]),
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )
        self._manifest = static_asset_manifest or {}
        self._env.globals["asset"] = self._asset_url

    @classmethod
    def from_config(cls, templates_dir: Path | None = None) -> "HTMLRenderer":
        from src.config import load_settings

        settings = load_settings()
        tdir = templates_dir or Path("templates")
        manifest_path = Path(settings.build_dir) / "asset-manifest.json"
        manifest: dict[str, str] = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text())
        return cls(templates_dir=tdir, static_asset_manifest=manifest)

    def _asset_url(self, name: str) -> str:
        return self._manifest.get(name, f"/daily-sports-page/static/{name}")

    def render(self, edition: Edition) -> str:
        """Render the edition to an HTML string. Deterministic — no side effects."""
        template = self._env.get_template("index.html.j2")
        html = template.render(edition=edition)
        logger.info("rendered edition %s (%d bytes)", edition.edition.id, len(html.encode()))
        return html

    def render_inline(self, edition: Edition, static_dir: Path | None = None) -> str:
        """Render with CSS and JS inlined — suitable for local file:// preview.

        The external <link rel="stylesheet"> and <script src="..."> tags are
        replaced with inline <style> and <script> blocks so the page works when
        opened directly from disk without a web server.
        """
        html = self.render(edition)
        sdir = static_dir or Path("static")

        css_path = sdir / "css" / "daily-sports-page.css"
        js_path = sdir / "js" / "daily-sports-page.js"

        # Replace stylesheet link with inline <style>
        if css_path.exists():
            css = css_path.read_text()
            html = re.sub(
                r'<link\s[^>]*rel=["\']stylesheet["\'][^>]*/?>',
                f"<style>\n{css}\n</style>",
                html,
                flags=re.IGNORECASE,
            )

        # Replace script src with inline <script>
        if js_path.exists():
            js = js_path.read_text()
            html = re.sub(
                r'<script\s[^>]*src=["\'][^"\']*daily-sports-page\.js["\'][^>]*>\s*</script>',
                f"<script>\n{js}\n</script>",
                html,
                flags=re.IGNORECASE,
            )

        return html

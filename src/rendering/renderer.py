# src/rendering/renderer.py
import json
import logging
from pathlib import Path
from src.models.edition import Edition
from src.rendering.html_renderer import HTMLRenderer

logger = logging.getLogger(__name__)


def render_from_file(edition_json_path: Path, output_dir: Path) -> Path:
    """Render HTML from an Edition JSON file. Pure function — no network, no AI."""
    raw = json.loads(edition_json_path.read_text(encoding="utf-8"))
    edition = Edition.model_validate(raw)
    renderer = HTMLRenderer.from_config()
    html = renderer.render(edition)
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / "index.html"
    out.write_text(html, encoding="utf-8")
    # Also write edition.json alongside HTML
    (output_dir / "edition.json").write_text(edition.model_dump_json(indent=2), encoding="utf-8")
    logger.info("wrote rendered HTML to %s", out)
    return out

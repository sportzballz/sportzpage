#!/usr/bin/env python3
"""Download and parse Baseball-Reference Bullpen history pages with Playwright."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import Page, async_playwright

from src.collectors.history import HistoryCollector

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "history" / "baseball_reference_urls.txt"
DEFAULT_OUTPUT = ROOT / "data" / "history" / "days"
DEFAULT_PROFILE = ROOT / ".playwright" / "history-profile"
CHALLENGE_TITLES = ("just a moment", "attention required")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("history-downloader")


def page_slug(url: str) -> str:
    slug = Path(urlparse(url).path).name
    if not slug or "_" not in slug:
        raise ValueError(f"invalid Bullpen URL: {url}")
    return slug


async def wait_for_content(page: Page, timeout_ms: int) -> str:
    """Wait for either Bullpen content or completion of a browser challenge."""
    await page.wait_for_load_state("domcontentloaded")
    title = (await page.title()).lower()
    if any(challenge in title for challenge in CHALLENGE_TITLES):
        logger.info("Cloudflare check detected; complete it in the Chromium window")
    await page.wait_for_selector(
        ".mw-parser-output, #mw-content-text, article",
        state="attached",
        timeout=timeout_ms,
    )
    return await page.content()


async def download(args: argparse.Namespace) -> int:
    urls = [
        line.strip()
        for line in args.manifest.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    if args.limit:
        urls = urls[: args.limit]
    args.output.mkdir(parents=True, exist_ok=True)
    args.profile.mkdir(parents=True, exist_ok=True)

    failures: list[dict[str, str]] = []
    completed = 0
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            str(args.profile),
            headless=args.headless,
            viewport={"width": 1440, "height": 1000},
        )
        page = context.pages[0] if context.pages else await context.new_page()

        for number, url in enumerate(urls, start=1):
            slug = page_slug(url)
            json_path = args.output / f"{slug}.json"
            html_path = args.output / "raw" / f"{slug}.html"
            if json_path.exists() and not args.force:
                logger.info("[%d/%d] skipping %s", number, len(urls), slug)
                continue

            logger.info("[%d/%d] downloading %s", number, len(urls), url)
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=args.timeout * 1000)
                html = await wait_for_content(page, args.timeout * 1000)
                collector = HistoryCollector.from_slug(slug)
                all_events = collector.parse(html)
                payload = {
                    "date": slug,
                    "source": url,
                    "item_count": len(all_events),
                    "items": all_events,
                }
                json_path.write_text(json.dumps(payload, indent=2) + "\n")
                if args.save_html:
                    html_path.parent.mkdir(parents=True, exist_ok=True)
                    html_path.write_text(html)
                completed += 1
            except Exception as exc:
                logger.error("failed %s: %s", slug, exc)
                failures.append({"url": url, "error": str(exc)})
            await asyncio.sleep(args.delay)

        await context.close()

    summary = {
        "requested": len(urls),
        "downloaded": completed,
        "failed": len(failures),
        "failures": failures,
    }
    (args.output / "download_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    logger.info("finished: %d downloaded, %d failed", completed, len(failures))
    return 1 if failures else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--limit", type=int, help="Process only the first N URLs")
    parser.add_argument("--delay", type=float, default=3.0, help="Seconds between pages")
    parser.add_argument("--timeout", type=int, default=120, help="Per-page timeout in seconds")
    parser.add_argument("--headless", action="store_true", help="Run without a visible browser")
    parser.add_argument("--force", action="store_true", help="Replace existing parsed files")
    parser.add_argument("--save-html", action="store_true", help="Also retain raw page HTML")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(download(parse_args())))

#!/usr/bin/env python3
"""Assemble the public teaser, rolling archive, and private current edition."""

from __future__ import annotations

import argparse
import html
import json
import shutil
from datetime import date
from pathlib import Path


ARCHIVE_LIMIT = 7


def _copy_tree(source: Path, destination: Path) -> None:
    if source.exists():
        shutil.copytree(source, destination, dirs_exist_ok=True)


def _edition_date(directory: Path) -> str | None:
    path = directory / "edition.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["edition"]["date"]
    try:
        date.fromisoformat(directory.name)
    except ValueError:
        return None
    return directory.name if (directory / "index.html").exists() else None


def _page(title: str, body: str, *, description: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#8b1e2d">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description)}">
  <link rel="icon" href="/static/icons/favicon.ico" sizes="any">
  <link rel="stylesheet" href="/static/css/daily-sports-page.css">
  <link rel="stylesheet" href="/static/css/subscription.css?v=20260821-layout-fix">
</head>
<body class="subscription-page">
  <header class="masthead">
    <p class="masthead-label">Independent Daily Coverage</p>
    <h1 class="masthead-title">The Daily Sports Page</h1>
    <p class="masthead-meta">Baseball &bull; Football &bull; Delivered Daily</p>
  </header>
  {body}
  <footer class="site-footer"><p>The Daily Sports Page</p></footer>
</body>
</html>
"""


def _landing(edition: dict, archive_dates: list[str]) -> str:
    metadata = edition["edition"]
    story = edition.get("lead_story") or {}
    headline = story.get("headline") or "Today’s Daily Sports Page is ready"
    deck = story.get("deck") or "Scores, standings, reporting, and analysis in one daily edition."
    archive = "".join(
        f'<li><a href="/archive/{day}/">{date.fromisoformat(day).strftime("%A, %B %-d, %Y")}</a></li>'
        for day in archive_dates
    ) or "<li>The first free archive edition will appear tomorrow.</li>"
    body = f"""
  <main class="subscription-shell" id="main-content">
    <section class="subscription-hero">
      <p class="edition-label">Today’s edition &bull; {html.escape(metadata['date'])}</p>
      <h2>{html.escape(headline)}</h2>
      <p class="subscription-deck">{html.escape(deck)}</p>
      <div class="teaser-fade" aria-hidden="true"></div>
      <a class="subscribe-button" href="/subscriber/current/">Read today’s complete edition — free preview</a>
      <p class="delivery-note">The subscription gate is temporarily disabled while editions are monitored.</p>
    </section>
    <section class="subscription-benefits">
      <h2>One daily sports page. Your choice of delivery.</h2>
      <ul>
        <li>Full baseball and football editions</li>
        <li>Protected web access from any device</li>
        <li>Full email edition or concise inbox digest</li>
        <li>Print-ready edition for reading offline</li>
      </ul>
    </section>
    <section class="free-archive">
      <p class="section-label">Read before you subscribe</p>
      <h2>Previous seven editions — free</h2>
      <ul>{archive}</ul>
    </section>
  </main>"""
    return _page(
        "The Daily Sports Page — Today’s Edition",
        body,
        description="Preview today’s sports page and read the previous seven editions free.",
    )


def _archive_index(archive_dates: list[str]) -> str:
    items = "".join(
        f'<article class="archive-card"><p>Free edition</p><h2><a href="/archive/{day}/">'
        f'{date.fromisoformat(day).strftime("%A, %B %-d, %Y")}</a></h2></article>'
        for day in archive_dates
    ) or '<p class="no-content">The rolling archive begins with the next daily publication.</p>'
    return _page(
        "Free Archive — The Daily Sports Page",
        f'<main class="subscription-shell"><p><a href="/">&larr; Today’s preview</a></p>'
        f'<section class="free-archive"><p class="section-label">Seven days free</p>'
        f'<h2>Recent editions</h2><div class="archive-grid">{items}</div></section></main>',
        description="Read the previous seven Daily Sports Page editions free.",
    )


def _subscribe_page() -> str:
    body = """
  <main class="subscription-shell">
    <section class="subscription-hero subscribe-panel">
      <p class="edition-label">Founding subscription</p>
      <h2>The complete daily edition for $2/month</h2>
      <p class="subscription-deck">Secure checkout is being connected. Today’s edition is temporarily available as a free preview.</p>
      <p>Subscribers will be able to read through a protected URL or choose a full HTML edition, concise digest, or print-ready delivery in their inbox.</p>
      <a class="subscribe-button" href="/subscriber/current/">Read today’s free preview</a>
      <p><a href="/archive/">Read the previous seven editions free</a></p>
    </section>
  </main>"""
    return _page(
        "Subscribe — The Daily Sports Page",
        body,
        description="Subscribe to The Daily Sports Page for $2 per month.",
    )


def _email_digest(edition: dict) -> str:
    metadata = edition["edition"]
    story = edition.get("lead_story") or {}
    headline = html.escape(story.get("headline") or "Today’s Daily Sports Page")
    deck = html.escape(story.get("deck") or "Your complete daily edition is ready.")
    return f"""<!doctype html><html><body style="font-family:Georgia,serif;color:#1a1a1a">
<div style="max-width:640px;margin:auto"><p style="font:700 12px Arial;color:#8b1e2d;text-transform:uppercase">{metadata['date']}</p>
<h1 style="border-bottom:4px double #444">The Daily Sports Page</h1><h2>{headline}</h2><p>{deck}</p>
<p><a href="https://thedailysportspage.com/subscriber/current/" style="background:#8b1e2d;color:white;padding:12px 18px;text-decoration:none">Read the complete edition</a></p>
<p style="font:12px Arial;color:#666">Subscriber access is required. Delivery preferences will be available after account activation.</p></div>
</body></html>"""


def assemble(build_dir: Path, football_dir: Path, static_dir: Path, previous: Path, output: Path) -> None:
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    edition = json.loads((build_dir / "edition.json").read_text(encoding="utf-8"))
    current_date = edition["edition"]["date"]

    archive_root = output / "archive"
    _copy_tree(previous / "archive", archive_root)
    archive_root.mkdir(parents=True, exist_ok=True)

    previous_current = previous / "subscriber" / "current"
    previous_date = _edition_date(previous_current)
    if previous_date and previous_date != current_date:
        _copy_tree(previous_current, archive_root / previous_date)

    archive_dates = sorted(
        (
            path.name
            for path in archive_root.iterdir()
            if path.is_dir() and _edition_date(path) and path.name < current_date
        ),
        reverse=True,
    )[:ARCHIVE_LIMIT]
    for path in list(archive_root.iterdir()):
        if path.is_dir() and path.name not in archive_dates:
            shutil.rmtree(path)

    current = output / "subscriber" / "current"
    current.mkdir(parents=True)
    shutil.copy2(build_dir / "index.html", current / "index.html")
    shutil.copy2(build_dir / "edition.json", current / "edition.json")
    _copy_tree(football_dir, current / "football")
    _copy_tree(static_dir, current / "static")

    delivery = output / "delivery" / "current"
    delivery.mkdir(parents=True)
    (delivery / "email.html").write_text(_email_digest(edition), encoding="utf-8")
    shutil.copy2(build_dir / "index.html", delivery / "full.html")
    shutil.copy2(build_dir / "index.html", delivery / "print.html")
    (delivery / "manifest.json").write_text(
        json.dumps(
            {
                "edition_date": current_date,
                "protected_url": "https://thedailysportspage.com/subscriber/current/",
                "formats": {
                    "digest_html": "email.html",
                    "full_html": "full.html",
                    "print_html": "print.html",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    _copy_tree(static_dir, output / "static")
    (output / "index.html").write_text(_landing(edition, archive_dates), encoding="utf-8")
    archive_root.mkdir(exist_ok=True)
    (archive_root / "index.html").write_text(_archive_index(archive_dates), encoding="utf-8")
    (archive_root / "manifest.json").write_text(
        json.dumps({"editions": archive_dates}, indent=2) + "\n", encoding="utf-8"
    )
    subscribe = output / "subscribe"
    subscribe.mkdir()
    (subscribe / "index.html").write_text(_subscribe_page(), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--football-dir", type=Path, default=Path("build/football"))
    parser.add_argument("--static-dir", type=Path, default=Path("static"))
    parser.add_argument("--previous-site", type=Path, default=Path("previous-site"))
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    assemble(args.build_dir, args.football_dir, args.static_dir, args.previous_site, args.output)


if __name__ == "__main__":
    main()

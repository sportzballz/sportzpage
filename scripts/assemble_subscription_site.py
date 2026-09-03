#!/usr/bin/env python3
"""Assemble the honor-supported homepage, rolling archive, and current edition."""

from __future__ import annotations

import argparse
import html
import json
import re
import shutil
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from src.markets import MARKETS

ARCHIVE_LIMIT = 7
SITE_URL = "https://thedailysportspage.com"


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


def _json_ld(payload: dict) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")


def _page(title: str, body: str, *, description: str, canonical: str) -> str:
    canonical_url = f"{SITE_URL}{canonical}"
    structured_data = _json_ld(
        {
            "@context": "https://schema.org",
            "@type": "WebPage",
            "name": title,
            "description": description,
            "url": canonical_url,
            "isPartOf": {"@type": "WebSite", "name": "The Daily Sports Page", "url": f"{SITE_URL}/"},
            "publisher": {"@type": "Organization", "name": "The Daily Sports Page", "url": f"{SITE_URL}/"},
        }
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#8b1e2d">
  <title>{html.escape(title)}</title>
  <meta name="description" content="{html.escape(description)}">
  <meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:site_name" content="The Daily Sports Page">
  <meta property="og:title" content="{html.escape(title)}">
  <meta property="og:description" content="{html.escape(description)}">
  <meta property="og:type" content="website">
  <meta property="og:url" content="{canonical_url}">
  <meta name="twitter:card" content="summary">
  <script type="application/ld+json">{structured_data}</script>
  <link rel="icon" href="/static/icons/favicon.ico" sizes="any">
  <link rel="stylesheet" href="/static/css/daily-sports-page.css?v=20260830-market-editions">
  <link rel="stylesheet" href="/static/css/subscription.css?v=20260830-market-editions">
</head>
<body class="subscription-page">
  <header class="masthead">
    <p class="masthead-label">Independent Daily Coverage</p>
    <h1 class="masthead-title">The Daily Sports Page</h1>
    <p class="masthead-meta">Baseball &bull; Football &bull; Delivered Daily</p>
  </header>
  {body}
  <footer class="site-footer"><p>The Daily Sports Page &bull; <a href="/privacy/">Privacy Policy</a></p></footer>
</body>
</html>
"""


def _privacy_policy() -> str:
    body = """
  <main class="subscription-shell" id="main-content">
    <article class="privacy-policy">
      <p class="section-label">Effective September 3, 2026</p>
      <h2>Privacy Policy</h2>
      <p>The Daily Sports Page respects your privacy. This policy explains what information may be processed when you use the website or iOS app, why it is used, and the choices available to you.</p>

      <h3>Information we process</h3>
      <p><strong>Website analytics.</strong> We use Cloudflare Web Analytics to understand aggregate traffic, such as page views, referring pages, approximate region, and browser or device type. The Daily Sports Page does not use this service to build advertising profiles or identify individual readers.</p>
      <p><strong>Reader feedback.</strong> If you submit a Letter to the Editor, we receive the category, message, page address, and submission time. A one-way daily hash derived from the network address is used only to enforce the limit of three submissions per day; the raw address is not stored in the feedback record.</p>
      <p><strong>Subscriptions.</strong> Purchases are processed by Apple through StoreKit. Apple handles payment and billing information. The app checks subscription product and entitlement information supplied by Apple, but The Daily Sports Page does not receive your payment-card details.</p>
      <p><strong>Preferences and offline content.</strong> Your selected market and downloaded edition may be stored on your device so the app and website remember your preferences and can provide offline reading.</p>
      <p><strong>Notifications.</strong> If you allow notifications, Apple supplies the app with a device token. The current app stores that token on your device and does not transmit it to The Daily Sports Page. You can disable notifications at any time in iOS Settings.</p>

      <h3>How information is used</h3>
      <ul>
        <li>Provide, maintain, and improve the sports page.</li>
        <li>Verify access to subscriber features.</li>
        <li>Respond to feedback and correct errors.</li>
        <li>Protect the feedback service from spam and abuse.</li>
        <li>Understand aggregate readership and site performance.</li>
      </ul>

      <h3>Retention</h3>
      <p>Reader feedback is retained for up to 180 days. Daily rate-limit records expire after approximately two days. Local preferences and cached editions remain on your device until the app data is removed or cleared. Apple and Cloudflare process information under their own retention practices.</p>

      <h3>Sharing and services</h3>
      <p>We do not sell personal information. Information is processed only as needed by service providers that operate the site and app, including Apple, Cloudflare, Amazon Web Services, and the email service used to deliver submitted feedback. The homepage also links to Buy Me a Coffee; information you provide there is governed by that service's privacy policy.</p>

      <h3>Your choices</h3>
      <p>You may decline notifications, avoid submitting feedback, clear website data, remove downloaded app data, or manage and cancel your subscription through your Apple Account. To ask a privacy question or request deletion of submitted feedback, use the <a href="/#feedback">Letter to the Editor</a> form and select General feedback.</p>

      <h3>Children</h3>
      <p>The Daily Sports Page is a general-audience sports publication and is not directed to children under 13. We do not knowingly request personal information from children.</p>

      <h3>Changes to this policy</h3>
      <p>We may update this policy as the service changes. The effective date at the top of this page will identify the latest version.</p>

      <p><a href="/">Return to The Daily Sports Page</a></p>
    </article>
  </main>
"""
    return _page(
        "Privacy Policy — The Daily Sports Page",
        body,
        description="Privacy practices for The Daily Sports Page website and iOS app.",
        canonical="/privacy/",
    )


def _landing(edition: dict, archive_dates: list[str]) -> str:
    metadata = edition["edition"]
    story = edition.get("lead_story") or {}
    headline = story.get("headline") or "Today’s Daily Sports Page is ready"
    deck = story.get("deck") or "Scores, standings, reporting, and analysis in one daily edition."
    archive = "".join(
        f'<li><a href="/archive/{day}/">{date.fromisoformat(day).strftime("%A, %B %-d, %Y")}</a></li>'
        for day in archive_dates
    ) or "<li>The first archive edition will appear tomorrow.</li>"
    body = f"""
  <main class="subscription-shell" id="main-content">
    <section class="subscription-hero">
      <p class="edition-label">Today’s edition &bull; {html.escape(metadata['date'])}</p>
      <h2>{html.escape(headline)}</h2>
      <p class="subscription-deck">{html.escape(deck)}</p>
      <a class="subscribe-button" data-current-edition-link href="/subscriber/current/">Read today’s complete edition</a>
      <p class="delivery-note">
        The Daily Sports Page is open to everyone and supported on the honor system.
      </p>
      <a class="support-button" href="https://buymeacoffee.com/thedailysportspage"
         target="_blank" rel="noopener noreferrer"
         aria-label="Buy The Daily Sports Page a beer, once or monthly (opens in a new tab)">
        Buy me a beer 🍻
      </a>
    </section>
    <section class="subscription-benefits">
      <h2>Independent daily coverage, open to everyone.</h2>
      <ul>
        <li>Full baseball and football editions</li>
        <li>Open web access from any device</li>
        <li>Support only when the coverage earns it</li>
        <li>Print-ready edition for reading offline</li>
      </ul>
    </section>
    <section class="feedback-panel" id="feedback">
      <p class="section-label">Letter to the Editor</p>
      <h2>Help shape the next edition</h2>
      <p>Spot an error, have a feature idea, or want to tell us what works? Send a note directly to the editor.</p>
      <form data-feedback-form>
        <label for="feedback-category">What is this about?</label>
        <select id="feedback-category" name="category">
          <option value="correction">Correction</option>
          <option value="feature">Feature request</option>
          <option value="design">Design or readability</option>
          <option value="general" selected>General feedback</option>
        </select>
        <label for="feedback-message">Your feedback</label>
        <textarea id="feedback-message" name="message" minlength="3" maxlength="3000" rows="5" required></textarea>
        <div class="feedback-honeypot" aria-hidden="true">
          <label for="feedback-website">Website</label>
          <input id="feedback-website" name="website" type="text" tabindex="-1" autocomplete="off">
        </div>
        <button class="feedback-button" type="submit">Send feedback</button>
        <p class="feedback-status" data-feedback-status role="status" aria-live="polite"></p>
      </form>
    </section>
    <section class="free-archive">
      <p class="section-label">Recent coverage</p>
      <h2>Last Week in Sports</h2>
      <ul>{archive}</ul>
    </section>
  </main>
  <script>
  try {{
    const market = localStorage.getItem('tdsp-market');
    const supported = ['philadelphia', 'boston', 'new-york', 'los-angeles', 'chicago', 'dallas'];
    if (supported.includes(market) && market !== 'philadelphia') {{
      document.querySelector('[data-current-edition-link]').href = `/editions/${{market}}/`;
    }}
  }} catch (_error) {{}}

  const feedbackForm = document.querySelector('[data-feedback-form]');
  if (feedbackForm) {{
    feedbackForm.addEventListener('submit', async (event) => {{
      event.preventDefault();
      const button = feedbackForm.querySelector('button[type="submit"]');
      const status = feedbackForm.querySelector('[data-feedback-status]');
      const fields = new FormData(feedbackForm);
      button.disabled = true;
      status.textContent = 'Sending…';
      try {{
        const response = await fetch('/api/feedback', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{
            category: fields.get('category'),
            message: fields.get('message'),
            website: fields.get('website'),
            page: window.location.pathname,
          }}),
        }});
        const result = await response.json();
        if (!response.ok || !result.ok) throw new Error(result.error || 'Unable to send feedback.');
        feedbackForm.reset();
        status.textContent = 'Thanks — your feedback was sent.';
      }} catch (error) {{
        status.textContent = error.message || 'Unable to send feedback right now. Please try again.';
      }} finally {{
        button.disabled = false;
      }}
    }});
  }}
  </script>"""
    return _page(
        "The Daily Sports Page — Today’s Edition",
        body,
        description="Read today’s complete sports page and the previous seven editions.",
        canonical="/",
    )


def _archive_index(archive_dates: list[str]) -> str:
    items = "".join(
        f'<article class="archive-card"><p>Daily edition</p><h2><a href="/archive/{day}/">'
        f'{date.fromisoformat(day).strftime("%A, %B %-d, %Y")}</a></h2></article>'
        for day in archive_dates
    ) or '<p class="no-content">The rolling archive begins with the next daily publication.</p>'
    return _page(
        "Archive — The Daily Sports Page",
        f'<main class="subscription-shell"><p><a href="/">&larr; Today’s edition</a></p>'
        f'<section class="free-archive"><p class="section-label">Recent coverage</p>'
        f'<h2>Recent editions</h2><div class="archive-grid">{items}</div></section></main>',
        description="Read the previous seven Daily Sports Page editions.",
        canonical="/archive/",
    )


def _apply_edition_seo(directory: Path, canonical_path: str) -> None:
    index_path = directory / "index.html"
    edition_path = directory / "edition.json"
    if not index_path.exists() or not edition_path.exists():
        return
    document = index_path.read_text(encoding="utf-8")
    if "</head>" not in document:
        return
    edition = json.loads(edition_path.read_text(encoding="utf-8"))
    metadata = edition["edition"]
    story = edition.get("lead_story") or {}
    headline = story.get("headline") or f"The Daily Sports Page — {metadata['date']}"
    description = story.get("deck") or "Daily MLB scores, standings, reporting, and analysis."
    canonical_url = f"{SITE_URL}{canonical_path}"
    structured_data = _json_ld(
        {
            "@context": "https://schema.org",
            "@type": "NewsArticle",
            "headline": headline,
            "description": description,
            "datePublished": metadata["date"],
            "dateModified": metadata["date"],
            "mainEntityOfPage": canonical_url,
            "author": {"@type": "Organization", "name": "The Daily Sports Page"},
            "publisher": {"@type": "Organization", "name": "The Daily Sports Page", "url": f"{SITE_URL}/"},
        }
    )
    document = re.sub(r"\n?\s*<!-- route-seo:start -->.*?<!-- route-seo:end -->", "", document, flags=re.S)
    document = re.sub(r"\n?\s*<link\s+rel=[\"']canonical[\"'][^>]*>", "", document, flags=re.I)
    document = re.sub(
        r"\n?\s*<meta\s+(?:name=[\"'](?:robots|twitter:card)[\"']|property=[\"']og:(?:site_name|title|description|type|url)[\"'])[^>]*>",
        "",
        document,
        flags=re.I,
    )
    document = re.sub(
        r"<title>.*?</title>",
        f"<title>{html.escape(headline, quote=False)} — The Daily Sports Page</title>",
        document,
        count=1,
        flags=re.I | re.S,
    )
    if not re.search(r"<title>.*?</title>", document, flags=re.I | re.S):
        document = document.replace(
            "<head>", f"<head><title>{html.escape(headline, quote=False)} — The Daily Sports Page</title>", 1
        )
    document = re.sub(
        r"<meta\s+name=[\"']description[\"'][^>]*>",
        f'<meta name="description" content="{html.escape(description)}">',
        document,
        count=1,
        flags=re.I,
    )
    if not re.search(r"<meta\s+name=[\"']description[\"']", document, flags=re.I):
        document = document.replace(
            "</head>", f'<meta name="description" content="{html.escape(description)}">\n</head>', 1
        )
    block = f"""
  <!-- route-seo:start -->
  <meta name="robots" content="index,follow,max-image-preview:large,max-snippet:-1,max-video-preview:-1">
  <link rel="canonical" href="{canonical_url}">
  <meta property="og:site_name" content="The Daily Sports Page">
  <meta property="og:title" content="{html.escape(headline)}">
  <meta property="og:description" content="{html.escape(description)}">
  <meta property="og:url" content="{canonical_url}">
  <meta property="og:type" content="article">
  <meta name="twitter:card" content="summary">
  <script type="application/ld+json">{structured_data}</script>
  <!-- route-seo:end -->
"""
    index_path.write_text(document.replace("</head>", f"{block}</head>", 1), encoding="utf-8")


def _remove_legacy_edition_support_link(directory: Path) -> None:
    """Keep support calls to action on the homepage, including for archived editions."""
    index_path = directory / "index.html"
    if not index_path.exists():
        return
    document = index_path.read_text(encoding="utf-8")
    document = re.sub(
        r"\s*<li\s+class=[\"']support-item[\"']>.*?</li>",
        "",
        document,
        flags=re.I | re.S,
    )
    index_path.write_text(document, encoding="utf-8")


def _write_discovery_files(output: Path, archive_dates: list[str], current_date: str) -> None:
    paths = [("/", current_date), ("/archive/", current_date)]
    paths.extend(
        [
            ("/subscriber/current/", current_date),
            ("/football/", current_date),
            ("/privacy/", current_date),
        ]
    )
    paths.extend((f"/archive/{day}/", day) for day in archive_dates)
    for market in MARKETS:
        paths.extend(
            [
                (f"/editions/{market.slug}/", current_date),
                (f"/editions/{market.slug}/football/", current_date),
            ]
        )
    urls = "".join(
        f"  <url><loc>{xml_escape(SITE_URL + path)}</loc><lastmod>{last_modified}</lastmod></url>\n"
        for path, last_modified in paths
    )
    (output / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{urls}</urlset>\n",
        encoding="utf-8",
    )
    (output / "robots.txt").write_text(
        "User-agent: *\nAllow: /\nDisallow: /delivery/\n"
        f"Sitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8",
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
<p style="font:12px Arial;color:#666">The Daily Sports Page is open to everyone and supported on the honor system.</p></div>
</body></html>"""


def assemble(
    build_dir: Path,
    football_dir: Path,
    static_dir: Path,
    previous: Path,
    output: Path,
    market_build_dir: Path | None = None,
    football_market_dir: Path | None = None,
) -> None:
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
                "edition_url": "https://thedailysportspage.com/subscriber/current/",
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
    editions_root = output / "editions"
    for market in MARKETS:
        market_source = market_build_dir / market.slug if market_build_dir else build_dir
        football_source = (
            football_market_dir / market.slug if football_market_dir else football_dir
        )
        if not (market_source / "index.html").exists():
            raise FileNotFoundError(f"missing generated market edition: {market_source}")
        market_route = editions_root / market.slug
        _copy_tree(market_source, market_route)
        _copy_tree(football_source, market_route / "football")
        _copy_tree(static_dir, market_route / "static")
        _remove_legacy_edition_support_link(market_route)
        _apply_edition_seo(market_route, f"/editions/{market.slug}/")
    (output / "index.html").write_text(_landing(edition, archive_dates), encoding="utf-8")
    privacy = output / "privacy"
    privacy.mkdir(parents=True, exist_ok=True)
    (privacy / "index.html").write_text(_privacy_policy(), encoding="utf-8")
    archive_root.mkdir(exist_ok=True)
    (archive_root / "index.html").write_text(_archive_index(archive_dates), encoding="utf-8")
    (archive_root / "manifest.json").write_text(
        json.dumps({"editions": archive_dates}, indent=2) + "\n", encoding="utf-8"
    )
    _remove_legacy_edition_support_link(current)
    _apply_edition_seo(current, "/subscriber/current/")
    for day in archive_dates:
        _remove_legacy_edition_support_link(archive_root / day)
        _apply_edition_seo(archive_root / day, f"/archive/{day}/")
    _write_discovery_files(output, archive_dates, current_date)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--build-dir", type=Path, default=Path("build"))
    parser.add_argument("--football-dir", type=Path, default=Path("build/football"))
    parser.add_argument("--market-build-dir", type=Path, default=Path("build/markets"))
    parser.add_argument(
        "--football-market-dir", type=Path, default=Path("build/football-markets")
    )
    parser.add_argument("--static-dir", type=Path, default=Path("static"))
    parser.add_argument("--previous-site", type=Path, default=Path("previous-site"))
    parser.add_argument("--output", type=Path, default=Path("dist"))
    args = parser.parse_args()
    assemble(
        args.build_dir,
        args.football_dir,
        args.static_dir,
        args.previous_site,
        args.output,
        market_build_dir=args.market_build_dir,
        football_market_dir=args.football_market_dir,
    )


if __name__ == "__main__":
    main()

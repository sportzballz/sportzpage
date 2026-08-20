#!/usr/bin/env python3
"""Generate the in-season Baseball-Reference Bullpen URL manifest."""

from datetime import date, timedelta
from pathlib import Path

BASE_URL = "https://www.baseball-reference.com/bullpen"
OUTPUT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "history"
    / "baseball_reference_urls.txt"
)


def generate_urls() -> list[str]:
    current = date(2001, 4, 1)  # The year is arbitrary; only month and day are used.
    end = date(2001, 10, 31)
    urls: list[str] = []
    while current <= end:
        urls.append(f"{BASE_URL}/{current.strftime('%B')}_{current.day}")
        current += timedelta(days=1)
    return urls


def main() -> None:
    urls = generate_urls()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(urls) + "\n")
    print(f"Wrote {len(urls)} URLs to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

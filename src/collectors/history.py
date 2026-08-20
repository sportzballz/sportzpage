from __future__ import annotations

import json
import logging
import random
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from src.history_text import split_sentences

logger = logging.getLogger(__name__)

BASE_URL = "https://www.baseball-reference.com/bullpen"
MIN_ITEMS = 8
MAX_ITEMS = 12
TARGET_CHARACTERS = 1200
PHILADELPHIA_TERMS = ("phillies", "philadelphia", "athletics", "phils")
YEAR_EVENT = re.compile(r"^(18\d{2}|19\d{2}|20\d{2})\s*[-–—:]\s*(.+)$")


class HistoryCollector:
    """Collect a small, date-specific set of events from the Baseball-Reference Bullpen."""

    def __init__(self, edition_date: date, timeout: float = 15.0) -> None:
        self._edition_date = edition_date
        self._timeout = timeout

    @classmethod
    def from_slug(cls, slug: str) -> HistoryCollector:
        month_name, day_text = slug.rsplit("_", 1)
        edition_date = datetime.strptime(f"2001-{month_name}-{day_text}", "%Y-%B-%d").date()
        return cls(edition_date)

    @property
    def source_url(self) -> str:
        return f"{BASE_URL}/{self._edition_date.strftime('%B')}_{self._edition_date.day}"

    async def collect(self) -> dict[str, Any]:
        slug = f"{self._edition_date.strftime('%B')}_{self._edition_date.day}"
        local_path = Path("data/history/days") / f"{slug}.json"
        if local_path.exists():
            local = json.loads(local_path.read_text())
            return {
                "source": local.get("source", self.source_url),
                "items": self.select_subset(local.get("items", [])),
            }
        headers = {
            "User-Agent": (
                "SportzBallz/1.0 (+https://sportzballz.io; "
                "daily baseball-history attribution)"
            )
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
                response = await client.get(self.source_url, follow_redirects=True)
                response.raise_for_status()
            events = self.parse(response.text)
            return {"source": self.source_url, "items": self.select_subset(events)}
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "Baseball-Reference history unavailable for %s: %s", self.source_url, exc
            )
            return {"source": self.source_url, "items": [], "error": str(exc)}

    def parse(self, html: str) -> list[dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        content = soup.select_one(".mw-parser-output") or soup
        events: list[dict[str, Any]] = []
        in_events = False

        for node in content.find_all(["h2", "h3", "li"]):
            if not isinstance(node, Tag):
                continue
            if node.name in {"h2", "h3"}:
                heading = node.get_text(" ", strip=True).lower()
                if "event" in heading:
                    in_events = True
                elif in_events and any(word in heading for word in ("birth", "death", "source")):
                    break
                continue
            if not in_events:
                continue
            text = " ".join(node.get_text(" ", strip=True).split())
            match = YEAR_EVENT.match(text)
            if match:
                events.append({"year": int(match.group(1)), "description": match.group(2)})

        if not events:
            raise ValueError("no dated events found on Bullpen page")
        return events

    @classmethod
    def separate_events(cls, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract one complete occurrence from each year-level source entry.

        Bullpen clubs every occurrence from a year into one list item. The first
        sentence is a standalone occurrence; later sentences may either support
        it or start unrelated events, so selecting them independently can produce
        contextless fragments. The complete database record remains unchanged.
        """
        separated: list[dict[str, Any]] = []
        for event in events:
            sentences = split_sentences(
                " ".join(str(event.get("description", "")).split())
            )
            if sentences:
                separated.append(
                    {"year": event.get("year"), "description": sentences[0]}
                )
        return separated

    def select_subset(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Fill the history column with a stable sample of separate events."""
        events = self.separate_events(events)
        if not events:
            return []
        rng = random.Random(self._edition_date.strftime("%B_%d"))  # noqa: S311
        philly = [
            event
            for event in events
            if any(term in event["description"].lower() for term in PHILADELPHIA_TERMS)
        ]
        selected = rng.sample(philly, k=1) if philly else []
        remaining = [event for event in events if event not in selected]
        rng.shuffle(remaining)
        for event in remaining:
            if len(selected) >= MAX_ITEMS:
                break
            selected.append(event)
            character_count = sum(len(item["description"]) for item in selected)
            if len(selected) >= MIN_ITEMS and character_count >= TARGET_CHARACTERS:
                break
        return selected

from __future__ import annotations

import asyncio
import html
import logging
import re
import xml.etree.ElementTree as ET
from typing import Any

import httpx

logger = logging.getLogger(__name__)

RSS_URL = "https://www.mlb.com/feeds/news/rss.xml"
HUMAN_INTEREST_TERMS = {
    "rookie",
    "prospect",
    "journey",
    "comeback",
    "history",
    "historic",
    "milestone",
    "family",
    "community",
    "dream",
    "story",
    "breakout",
    "award",
    "fan",
    "girl",
    "women",
    "children",
    "hometown",
    "special cleats",
    "having fun",
}
LOW_VALUE_TERMS = {
    "power rankings",
    "odds",
    "betting",
    "fantasy",
    "probable pitchers",
    "injury",
    "injuries",
    "out for season",
    "miss rest of season",
}


class NewsCollector:
    """Collect a small, current set of official MLB feature stories."""

    def __init__(self, limit: int = 6, timeout: float = 15.0) -> None:
        self._limit = limit
        self._timeout = timeout

    async def collect(self) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                response = await client.get(RSS_URL)
                response.raise_for_status()
                candidates = self._parse_feed(response.content)
                selected = sorted(candidates, key=self._score, reverse=True)[: self._limit]
                summaries = await asyncio.gather(
                    *(self._fetch_summary(client, item["link"]) for item in selected)
                )
            for item, summary in zip(selected, summaries):
                item["summary"] = summary or f"Read the latest feature from MLB.com: {item['title']}"
            return {"source": "MLB.com", "items": selected}
        except Exception as exc:
            logger.warning("MLB news feed unavailable, continuing without: %s", exc)
            return {"source": "MLB.com", "items": []}

    def _parse_feed(self, content: bytes) -> list[dict[str, str]]:
        root = ET.fromstring(content)
        items = []
        for node in root.findall("./channel/item"):
            title = (node.findtext("title") or "").strip()
            link = (node.findtext("link") or "").strip()
            if title and link:
                items.append(
                    {
                        "title": title,
                        "link": link,
                        "author": (node.findtext("{*}creator") or "MLB.com").strip() or "MLB.com",
                        "published": (node.findtext("pubDate") or "").strip(),
                    }
                )
        return items

    def _score(self, item: dict[str, str]) -> tuple[int, str]:
        title = item["title"].lower()
        score = sum(3 for term in HUMAN_INTEREST_TERMS if term in title)
        score -= sum(5 for term in LOW_VALUE_TERMS if term in title)
        return score, item.get("published", "")

    async def _fetch_summary(self, client: httpx.AsyncClient, url: str) -> str:
        try:
            response = await client.get(url)
            response.raise_for_status()
            match = re.search(
                r'<meta\s+(?:name="description"|property="og:description")\s+content="([^"]+)"',
                response.text,
                flags=re.IGNORECASE,
            )
            if not match:
                return ""
            summary = html.unescape(match.group(1))
            return " ".join(summary.split())
        except Exception as exc:
            logger.debug("news summary unavailable for %s: %s", url, exc)
            return ""

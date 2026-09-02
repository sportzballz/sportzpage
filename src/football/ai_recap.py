from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)
SUMMARY_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/summary"


class FootballLeadStoryService:
    """Create one ESPN-grounded NFL lead and reuse it for the edition day."""

    def __init__(
        self,
        *,
        model: str | None = None,
        api_key: str | None = None,
        cache_dir: Path | None = None,
        timeout: float = 45.0,
    ) -> None:
        self._model = model or os.getenv("AI_MODEL") or "gpt-5-mini"
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._cache_dir = cache_dir or Path(os.getenv("AI_CACHE_DIR", "build/ai-cache"))
        self._timeout = timeout

    def cache_path(self, game: dict[str, Any], edition_date: str) -> Path:
        return self._cache_dir / f"nfl-{edition_date}-{game['id']}.json"

    def news_cache_path(self, article: dict[str, Any], edition_date: str) -> Path:
        return self._cache_dir / f"nfl-news-{edition_date}-{article['id']}.json"

    async def generate(self, game: dict[str, Any], edition_date: str) -> dict[str, Any] | None:
        cached = self._load_cached(game, edition_date)
        if cached:
            logger.info("reusing cached NFL lead story for ESPN game %s", game["id"])
            return cached
        if not self._api_key:
            logger.warning("OPENAI_API_KEY is not configured; using deterministic NFL lead")
            return None
        source = await self._fetch_recap(str(game["id"]))
        if not source:
            return None
        try:
            generated = await self._rewrite(source, game, edition_date)
        except (ValueError, httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.warning("NFL lead rewrite unavailable for game %s: %s", game["id"], exc)
            return None
        self._save_cached(game, edition_date, generated)
        return generated

    async def generate_from_game_facts(
        self, game: dict[str, Any], edition_date: str, facts: str
    ) -> dict[str, Any] | None:
        """Rewrite collected scoreboard facts when ESPN has no recap article."""
        if not self._api_key:
            return None
        try:
            generated = await self._rewrite(facts, game, edition_date)
        except (ValueError, httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.warning("NFL fact rewrite unavailable for game %s: %s", game["id"], exc)
            return None
        self._save_cached(game, edition_date, generated)
        return generated

    async def generate_from_news(
        self, article: dict[str, Any], edition_date: str
    ) -> dict[str, Any] | None:
        """Create a self-contained lead from a current ESPN NFL news article."""
        cached = self._load_news_cached(article, edition_date)
        if cached:
            logger.info("reusing cached NFL news lead for ESPN article %s", article["id"])
            return cached
        if not self._api_key:
            logger.warning("OPENAI_API_KEY is not configured; NFL news lead unavailable")
            return None
        source = await self._fetch_news_article(article.get("api_url", ""))
        if not source:
            return None
        try:
            generated = await self._rewrite_news(source, article, edition_date)
        except (ValueError, httpx.HTTPError, json.JSONDecodeError) as exc:
            logger.warning("NFL news rewrite unavailable for article %s: %s", article["id"], exc)
            return None
        self._save_news_cached(article, edition_date, generated)
        return generated

    def _load_cached(self, game: dict[str, Any], edition_date: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(self.cache_path(game, edition_date).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        required = {"headline", "deck", "paragraphs", "ai_generated"}
        if required <= payload.keys() and payload["ai_generated"] is True:
            payload.pop("url", None)
            payload.pop("source_url", None)
            return payload
        return None

    def _save_cached(self, game: dict[str, Any], edition_date: str, story: dict[str, Any]) -> None:
        path = self.cache_path(game, edition_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(story, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    def _load_news_cached(
        self, article: dict[str, Any], edition_date: str
    ) -> dict[str, Any] | None:
        try:
            payload = json.loads(
                self.news_cache_path(article, edition_date).read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            return None
        required = {"headline", "deck", "paragraphs", "ai_generated", "espn_news_id"}
        if required <= payload.keys() and payload["ai_generated"] is True:
            payload.pop("url", None)
            payload.pop("source_url", None)
            return payload
        return None

    def _save_news_cached(
        self, article: dict[str, Any], edition_date: str, story: dict[str, Any]
    ) -> None:
        path = self.news_cache_path(article, edition_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(story, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    async def _fetch_recap(self, game_id: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                response = await client.get(SUMMARY_URL, params={"event": game_id})
                response.raise_for_status()
            article = response.json().get("article") or {}
            story = article.get("story")
            if not story:
                return None
            return BeautifulSoup(str(story), "html.parser").get_text(" ", strip=True)
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ESPN NFL recap unavailable for %s: %s", game_id, exc)
            return None

    async def _fetch_news_article(self, api_url: str) -> str | None:
        if not api_url.startswith("https://content.core.api.espn.com/"):
            return None
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                response = await client.get(api_url)
                response.raise_for_status()
            payload = response.json()
            article = (payload.get("headlines") or [payload])[0]
            story = article.get("story")
            if not story:
                return None
            text = BeautifulSoup(str(story), "html.parser").get_text(" ", strip=True)
            return text if len(text) >= 200 else None
        except (httpx.HTTPError, ValueError, IndexError) as exc:
            logger.warning("ESPN NFL news article unavailable: %s", exc)
            return None

    async def _rewrite(
        self, source: str, game: dict[str, Any], edition_date: str
    ) -> dict[str, Any]:
        prompt = (
            "Rewrite this ESPN NFL recap as an original, self-contained newspaper game story. "
            "Use only facts in the supplied recap and game facts. Return a strong headline, "
            "a one-sentence deck, and 3 to 5 substantive paragraphs. Write in the clear, vivid "
            "voice of an experienced sports journalist. Do not mention ESPN or the "
            "rewriting process.\n\n"
            f"Edition date: {edition_date}\nGame: {game['away']['name']} {game['away']['score']} "
            f"at {game['home']['name']} {game['home']['score']}\nVenue: {game['venue']}\n\n"
            f"Source recap:\n{source}"
        )
        schema = {
            "type": "object",
            "properties": {
                "headline": {"type": "string"},
                "deck": {"type": "string"},
                "paragraphs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 3,
                    "maxItems": 5,
                },
            },
            "required": ["headline", "deck", "paragraphs"],
            "additionalProperties": False,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "input": prompt,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "football_lead_story",
                            "strict": True,
                            "schema": schema,
                        }
                    },
                },
            )
            response.raise_for_status()
        story = json.loads(self._output_text(response.json()))
        paragraphs = [str(value).strip() for value in story.get("paragraphs", [])]
        if not 3 <= len(paragraphs) <= 5 or not all(paragraphs):
            raise ValueError("NFL lead must contain three to five paragraphs")
        story.update(
            {
                "paragraphs": paragraphs,
                "ai_generated": True,
                "espn_game_id": str(game["id"]),
                "edition_date": edition_date,
            }
        )
        return story

    async def _rewrite_news(
        self, source: str, article: dict[str, Any], edition_date: str
    ) -> dict[str, Any]:
        prompt = (
            "Write an original, self-contained NFL newspaper story in the voice of an experienced "
            "sports journalist. Use only facts in the supplied source article; do not copy its "
            "phrasing, speculate, add quotes, or mention ESPN or the rewriting process. Return a "
            "strong headline, a one-sentence deck, and 3 to 5 substantive paragraphs. The result "
            "must give a TDSP reader the complete story without needing to follow an external "
            "link.\n\n"
            f"Edition date: {edition_date}\nSource headline: {article['headline']}\n"
            f"Source description: {article.get('description', '')}\n\nSource article:\n{source}"
        )
        schema = {
            "type": "object",
            "properties": {
                "headline": {"type": "string"},
                "deck": {"type": "string"},
                "paragraphs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 3,
                    "maxItems": 5,
                },
            },
            "required": ["headline", "deck", "paragraphs"],
            "additionalProperties": False,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": self._model,
                    "input": prompt,
                    "text": {
                        "format": {
                            "type": "json_schema",
                            "name": "football_news_lead_story",
                            "strict": True,
                            "schema": schema,
                        }
                    },
                },
            )
            response.raise_for_status()
        story = json.loads(self._output_text(response.json()))
        paragraphs = [str(value).strip() for value in story.get("paragraphs", [])]
        if not 3 <= len(paragraphs) <= 5 or not all(paragraphs):
            raise ValueError("NFL news lead must contain three to five paragraphs")
        story.update(
            {
                "paragraphs": paragraphs,
                "ai_generated": True,
                "espn_news_id": str(article["id"]),
                "source_kind": "nfl_news",
                "edition_date": edition_date,
            }
        )
        return story

    @staticmethod
    def _output_text(payload: dict[str, Any]) -> str:
        for item in payload.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return str(content["text"])
        raise ValueError("OpenAI response did not contain output text")

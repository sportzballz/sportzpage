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

    def _load_cached(self, game: dict[str, Any], edition_date: str) -> dict[str, Any] | None:
        try:
            payload = json.loads(self.cache_path(game, edition_date).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        required = {"headline", "deck", "paragraphs", "ai_generated"}
        return payload if required <= payload.keys() and payload["ai_generated"] is True else None

    def _save_cached(self, game: dict[str, Any], edition_date: str, story: dict[str, Any]) -> None:
        path = self.cache_path(game, edition_date)
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

    async def _rewrite(
        self, source: str, game: dict[str, Any], edition_date: str
    ) -> dict[str, Any]:
        prompt = (
            "Rewrite this ESPN NFL recap as an original, lively newspaper game synopsis. "
            "Use only facts in the supplied recap and game facts. Return a strong headline, "
            "a one-sentence deck, and exactly 3 short paragraphs. Do not mention ESPN or the "
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
                    "maxItems": 3,
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
        if len(paragraphs) != 3 or not all(paragraphs):
            raise ValueError("NFL lead must contain exactly three paragraphs")
        story.update(
            {
                "paragraphs": paragraphs,
                "url": game["recap_url"],
                "ai_generated": True,
                "espn_game_id": str(game["id"]),
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

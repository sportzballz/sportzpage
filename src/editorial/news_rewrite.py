from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path

import httpx

from src.models.story import Story, StoryType

logger = logging.getLogger(__name__)


class NewsStoryRewriteService:
    """Turn MLB news summaries into original, self-contained cached briefs."""

    def __init__(
        self,
        model: str | None = None,
        timeout: float = 45.0,
        api_key: str | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self._model = model
        self._timeout = timeout
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._cache_dir = cache_dir or Path(os.getenv("AI_CACHE_DIR", "build/ai-cache"))

    async def rewrite_all(self, stories: list[Story]) -> list[Story]:
        if not self._api_key:
            logger.warning("OPENAI_API_KEY is not configured; Around the League will be empty")
            return []
        results = await asyncio.gather(*(self.rewrite(story) for story in stories))
        return [story for story in results if story is not None]

    async def rewrite(self, source: Story) -> Story | None:
        cached = self._load_cached(source)
        if cached:
            logger.info("reusing cached Around the League brief for %s", source.headline)
            return cached
        try:
            text = await self._rewrite_with_openai(self._prompt(source))
            story = self._build_story(text, source)
            self._save_cached(source, story)
            return story
        except (
            OSError,
            TimeoutError,
            KeyError,
            ValueError,
            json.JSONDecodeError,
            httpx.HTTPError,
        ) as exc:
            logger.warning("Around the League rewrite unavailable for %s: %s", source.headline, exc)
            return None

    def cache_path(self, source: Story) -> Path:
        identity = next(iter(source.source_data_references), source.headline)
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
        return self._cache_dir / f"mlb-news-{digest}.json"

    def _load_cached(self, source: Story) -> Story | None:
        try:
            story = Story.model_validate_json(self.cache_path(source).read_text(encoding="utf-8"))
            return story if story.ai_generated and not story.source_url else None
        except (OSError, ValueError):
            return None

    def _save_cached(self, source: Story, story: Story) -> None:
        path = self.cache_path(source)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(story.model_dump_json(indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)

    async def _rewrite_with_openai(self, prompt: str) -> str:
        schema = {
            "type": "object",
            "properties": {
                "headline": {"type": "string"},
                "deck": {"type": "string"},
                "paragraphs": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 1,
                    "maxItems": 2,
                },
            },
            "required": ["headline", "deck", "paragraphs"],
            "additionalProperties": False,
        }
        payload = {
            "model": self._model or "gpt-5-mini",
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "around_the_league_brief",
                    "strict": True,
                    "schema": schema,
                }
            },
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
            )
            response.raise_for_status()
        result = response.json()
        for item in result.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return str(content["text"])
        raise ValueError("OpenAI response did not contain output text")

    def _build_story(self, text: str, source: Story) -> Story:
        payload = json.loads(text)
        paragraphs = [str(value).strip() for value in payload["paragraphs"] if str(value).strip()]
        if not 1 <= len(paragraphs) <= 2:
            raise ValueError("Around the League brief must contain one or two paragraphs")
        source_text = " ".join([source.headline, source.deck, *source.paragraphs])
        generated_text = " ".join([payload["headline"], payload["deck"], *paragraphs])
        self._validate_numbers(generated_text, source_text)
        source_id = self.cache_path(source).stem.removeprefix("mlb-news-")
        return Story(
            headline=str(payload["headline"]).strip(),
            deck=str(payload["deck"]).strip(),
            byline="Daily Sports Page Staff",
            paragraphs=paragraphs,
            source_data_references=[f"mlb-news:{source_id}"],
            story_type=StoryType.editorial,
            teams=source.teams,
            players=source.players,
            facts_used=source.facts_used,
            ai_generated=True,
            source_name="MLB.com reporting",
            source_url=None,
        )

    @staticmethod
    def _validate_numbers(generated: str, source: str) -> None:
        import re

        unsupported = set(re.findall(r"\b\d+(?:\.\d+)?\b", generated)) - set(
            re.findall(r"\b\d+(?:\.\d+)?\b", source)
        )
        if unsupported:
            raise ValueError(
                f"unsupported numbers in Around the League brief: {sorted(unsupported)}"
            )

    @staticmethod
    def _prompt(source: Story) -> str:
        facts = " ".join([source.headline, source.deck, *source.paragraphs])
        return f"""You are writing an Around the League brief for The Daily Sports Page.
Rewrite the supplied MLB.com summary into original newspaper copy. Use a crisp, informed
sports-journalist voice without imitating or naming a specific writer. Return ONLY valid JSON
with keys headline, deck, and paragraphs. paragraphs must contain one or two concise
paragraphs. Keep the story self-contained. Do not mention or link to MLB.com, invite the reader
to read elsewhere, copy distinctive phrases, or add facts, quotations, numbers, statistics,
timelines, or conclusions absent from the source.

Source facts:
{facts[:5000]}
"""

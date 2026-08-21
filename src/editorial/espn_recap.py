from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from dataclasses import dataclass
from typing import Any

import httpx
from bs4 import BeautifulSoup

from src.models.game import Game
from src.models.story import GameRecap, StoryType

logger = logging.getLogger(__name__)
ESPN_RECAP_URL = "https://www.espn.com/mlb/recap/_/gameId/{game_id}"
ESPN_SUMMARY_URL = (
    "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary?event={game_id}"
)


@dataclass
class ESPNRecap:
    game_id: str
    headline: str
    body: str
    source_url: str


class ESPNLeadStoryService:
    """Fetch an ESPN recap and turn it into an original newspaper lead synopsis."""

    def __init__(
        self,
        provider: str = "openclaw",
        model: str | None = None,
        timeout: float = 45.0,
        api_key: str | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._timeout = timeout
        self._api_key = api_key or os.getenv("OPENAI_API_KEY")

    async def generate(self, game: Game) -> GameRecap | None:
        if not game.espn_game_id:
            return None
        recap = await self.fetch(game.espn_game_id)
        if not recap:
            return None
        return await self.rewrite(recap, game)

    async def fetch(self, espn_game_id: str) -> ESPNRecap | None:
        source_url = ESPN_RECAP_URL.format(game_id=espn_game_id)
        try:
            async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
                summary = await client.get(ESPN_SUMMARY_URL.format(game_id=espn_game_id))
                summary.raise_for_status()
                story = self.parse_summary(summary.json())
                if not story:
                    response = await client.get(
                        source_url, headers={"User-Agent": "Mozilla/5.0"}
                    )
                    response.raise_for_status()
                    story = self.parse_page(response.text)
            if not story:
                return None
            return ESPNRecap(
                game_id=espn_game_id,
                headline=str(story.get("hdln", "")).strip(),
                body=self._plain_text(str(story.get("bdy", ""))),
                source_url=source_url,
            )
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("ESPN recap unavailable for %s: %s", espn_game_id, exc)
            return None

    @staticmethod
    def parse_summary(payload: dict[str, Any]) -> dict[str, Any] | None:
        article = payload.get("article")
        if not isinstance(article, dict) or not article.get("story"):
            return None
        return {"hdln": article.get("headline", ""), "bdy": article["story"]}

    @staticmethod
    def parse_page(html: str) -> dict[str, Any] | None:
        marker = "window['__espnfitt__']="
        soup = BeautifulSoup(html, "html.parser")
        for script in soup.find_all("script"):
            text = script.string or script.get_text()
            if marker not in text:
                continue
            encoded = text.split(marker, 1)[1].strip()
            if encoded.endswith(";"):
                encoded = encoded[:-1]
            payload = json.loads(encoded)
            return ESPNLeadStoryService._find_story(payload)
        return None

    @staticmethod
    def _find_story(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict):
            story = value.get("fullGmStry")
            if isinstance(story, dict) and story.get("bdy"):
                return story
            for child in value.values():
                found = ESPNLeadStoryService._find_story(child)
                if found:
                    return found
        elif isinstance(value, list):
            for child in value:
                found = ESPNLeadStoryService._find_story(child)
                if found:
                    return found
        return None

    @staticmethod
    def _plain_text(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        for heading in soup.find_all("hl2"):
            heading.replace_with("\n\n" + heading.get_text(" ", strip=True) + "\n")
        return "\n".join(line.strip() for line in soup.get_text(" ").splitlines() if line.strip())

    async def rewrite(self, recap: ESPNRecap, game: Game) -> GameRecap | None:
        prompt = self._prompt(recap, game)
        try:
            if self._provider == "openai":
                text = await self._rewrite_with_openai(prompt)
            else:
                text = await self._rewrite_with_openclaw(prompt)
            return self._build_game_recap(text, recap, game)
        except (
            OSError,
            TimeoutError,
            KeyError,
            ValueError,
            json.JSONDecodeError,
            httpx.HTTPError,
        ) as exc:
            logger.warning("lead-story rewrite unavailable for game %s: %s", game.game_id, exc)
            return None

    async def _rewrite_with_openclaw(self, prompt: str) -> str:
        command = ["openclaw", "infer", "model", "run", "--local", "--json"]
        if self._model:
            command.extend(["--model", self._model])
        command.extend(["--prompt", prompt])
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=self._timeout)
        if process.returncode != 0:
            raise OSError(f"local LLM failed: {stderr.decode(errors='replace')[-500:]}")
        result = json.loads(stdout)
        return str((result.get("outputs") or [{}])[0].get("text", ""))

    async def _rewrite_with_openai(self, prompt: str) -> str:
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY is not configured")
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
        payload = {
            "model": self._model or "gpt-5-mini",
            "input": prompt,
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "baseball_lead_story",
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
        return self._extract_output_text(result)

    @staticmethod
    def _extract_output_text(result: dict[str, Any]) -> str:
        for item in result.get("output", []):
            for content in item.get("content", []):
                if content.get("type") == "output_text" and content.get("text"):
                    return str(content["text"])
        raise ValueError("OpenAI response did not contain output text")

    def _build_game_recap(self, text: str, recap: ESPNRecap, game: Game) -> GameRecap:
        story = self._parse_model_json(text)
        paragraphs = [str(p).strip() for p in story.get("paragraphs", []) if str(p).strip()]
        if not 3 <= len(paragraphs) <= 5:
            raise ValueError("LLM synopsis must contain 3 to 5 paragraphs")
        generated_text = " ".join(
            [str(story.get("headline", "")), str(story.get("deck", "")), *paragraphs]
        )
        self._validate_grounding(generated_text, recap.body)
        winner = game.home if (game.home.runs or 0) > (game.away.runs or 0) else game.away
        loser = game.away if winner is game.home else game.home
        return GameRecap(
            headline=str(story["headline"]).strip(),
            deck=str(story["deck"]).strip(),
            byline="SportzBallz Staff",
            paragraphs=paragraphs,
            source_data_references=[f"game:{game.game_id}", f"espn:{recap.game_id}"],
            story_type=StoryType.game_recap,
            teams=[game.away.team_abbr, game.home.team_abbr],
            facts_used=[
                f"home_runs:{game.home.runs}",
                f"away_runs:{game.away.runs}",
                f"espn_game_id:{recap.game_id}",
            ],
            ai_generated=True,
            source_name="ESPN recap",
            source_url=recap.source_url,
            game_id=game.game_id,
            final_score=f"{winner.team_abbr} {winner.runs}, {loser.team_abbr} {loser.runs}",
            winning_pitcher=game.winning_pitcher,
            losing_pitcher=game.losing_pitcher,
            save_pitcher=game.save_pitcher,
            tags=list(game.tags),
        )

    @staticmethod
    def _parse_model_json(text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(cleaned)

    @staticmethod
    def _validate_grounding(generated: str, source: str) -> None:
        """Reject common small-model embellishments before they reach the front page."""
        source_lower = source.lower()
        unsupported_numbers = set(re.findall(r"\b\d+(?:\.\d+)?\b", generated)) - set(
            re.findall(r"\b\d+(?:\.\d+)?\b", source)
        )
        if unsupported_numbers:
            raise ValueError(f"unsupported numbers in synopsis: {sorted(unsupported_numbers)}")
        guarded_phrases = (
            "franchise record",
            "division rivals",
            "clinched",
            "clinching",
            "historic milestone",
            "winning streak",
        )
        for phrase in guarded_phrases:
            if phrase in generated.lower() and phrase not in source_lower:
                raise ValueError(f"unsupported claim in synopsis: {phrase}")

    @staticmethod
    def _prompt(recap: ESPNRecap, game: Game) -> str:
        return f"""You are writing the lead game story for The Daily Sportz Page.
Create an original synopsis based only on the supplied ESPN recap facts. Do not copy ESPN
sentences or distinctive phrases. Use a classic American baseball beat-writer voice: vivid,
economical, observant, and newspaper-ready, without imitating or naming a specific writer.
Return ONLY valid JSON with keys headline, deck, and paragraphs. paragraphs must be an array
of 3 to 5 substantial paragraphs. Do not add facts, quotations, or statistics absent below.
Never claim a clinch, title, standings change, streak, perfect game, or milestone unless the
source explicitly states it. Preserve whether a streak started, continued, or ended.

MLB game ID: {game.game_id}
ESPN game ID: {recap.game_id}
Matchup: {game.away.team_name} at {game.home.team_name}
Final: {game.away.team_abbr} {game.away.runs}, {game.home.team_abbr} {game.home.runs}
ESPN headline: {recap.headline}
Write paragraph one about the result and defining performance, paragraph two about how the
runs scored, and paragraph three about the pitching finish and other explicitly stated facts.
Do not infer that the teams are rivals. Do not connect a person to a city unless the source
explicitly says that person is from that city. Keep every action in its stated inning and
preserve who performed it. Every number in your JSON must occur in the source text.

ESPN recap facts (the source ends before its separate Up next section):
{recap.body.split('Up next', 1)[0][:12000]}
"""

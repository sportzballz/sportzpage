import json
from pathlib import Path

import pytest

from src.editorial.news_rewrite import NewsStoryRewriteService
from src.models.story import Story, StoryType


def source_story() -> Story:
    return Story(
        headline="Rookie completes a remarkable journey",
        deck="A rookie reached the Majors after an unusual path through baseball.",
        paragraphs=["A rookie reached the Majors after an unusual path through baseball."],
        source_data_references=["https://www.mlb.com/news/example"],
        story_type=StoryType.editorial,
        ai_generated=False,
        source_url="https://www.mlb.com/news/example",
    )


@pytest.mark.asyncio
async def test_rewrites_news_without_external_url_and_caches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = NewsStoryRewriteService(api_key="unused", cache_dir=tmp_path)

    async def rewrite(_prompt: str) -> str:
        return json.dumps(
            {
                "headline": "A Long Road Reaches the Majors",
                "deck": "One rookie's unusual path ended in the big leagues.",
                "paragraphs": ["The rookie completed an unusual journey to the Majors."],
            }
        )

    monkeypatch.setattr(service, "_rewrite_with_openai", rewrite)
    result = await service.rewrite(source_story())

    assert result is not None
    assert result.ai_generated is True
    assert result.source_url is None
    assert result.source_data_references[0].startswith("mlb-news:")
    assert service.cache_path(source_story()).exists()


@pytest.mark.asyncio
async def test_reuses_cached_news_without_openai(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    service = NewsStoryRewriteService(api_key="unused", cache_dir=tmp_path)
    cached = source_story().model_copy(
        update={"headline": "Cached brief", "ai_generated": True, "source_url": None}
    )
    service._save_cached(source_story(), cached)

    async def should_not_rewrite(_prompt: str) -> str:
        raise AssertionError("OpenAI must not be called for a cached league brief")

    monkeypatch.setattr(service, "_rewrite_with_openai", should_not_rewrite)
    result = await service.rewrite(source_story())

    assert result is not None
    assert result.headline == "Cached brief"


@pytest.mark.asyncio
async def test_missing_key_publishes_empty_league_section(tmp_path: Path) -> None:
    service = NewsStoryRewriteService(api_key="", cache_dir=tmp_path)

    assert await service.rewrite_all([source_story()]) == []

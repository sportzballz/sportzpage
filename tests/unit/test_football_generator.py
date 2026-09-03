from datetime import date
from pathlib import Path

import httpx
import pytest

from src.football.ai_recap import FootballLeadStoryService
from src.football.generator import FootballEditionGenerator


def test_support_link_is_not_in_football_menu() -> None:
    template = Path("templates/football.html.j2").read_text()
    assert "buymeacoffee.com" not in template
    assert "Buy me a beer" not in template


def test_football_page_contains_stories_without_espn_links() -> None:
    template = Path("templates/football.html.j2").read_text()

    assert "espn.com" not in template
    assert "page.lead.url" not in template
    assert "row.url" not in template
    assert "story.url" not in template


def test_around_the_nfl_renders_complete_rewritten_briefs() -> None:
    template = Path("templates/football.html.j2").read_text()

    assert "story.deck" in template
    assert "story.paragraphs" in template
    assert "story.description" not in template


def _event(event_id: str, away: str, home: str, completed: bool = True) -> dict:
    return {
        "id": event_id,
        "name": f"{away} at {home}",
        "date": "2026-08-20T23:00Z",
        "competitions": [{
            "venue": {"fullName": "The Linc"},
            "competitors": [
                {"homeAway": "away", "score": "17", "winner": False, "team": {"abbreviation": away, "displayName": away}},
                {"homeAway": "home", "score": "24", "winner": True, "team": {"abbreviation": home, "displayName": home}},
            ],
            "status": {"type": {"description": "Final", "completed": completed}},
        }],
    }


def test_parses_espn_nfl_scoreboard_event() -> None:
    games = FootballEditionGenerator._games({"events": [_event("401", "NYG", "PHI")]})

    assert games[0]["home"]["abbr"] == "PHI"
    assert games[0]["home"]["score"] == "24"
    assert games[0]["venue"] == "The Linc"
    assert "recap_url" not in games[0]
    assert games[0]["date"] == "2026-08-20"
    assert games[0]["date_label"] == "Thu, Aug 20"


def test_week_context_uses_espn_calendar_label() -> None:
    payload = {
        "week": {"number": 4},
        "leagues": [{
            "season": {"year": 2026, "type": {"id": "1", "name": "Preseason"}},
            "calendar": [{
                "value": "1",
                "entries": [{
                    "value": "4",
                    "label": "Preseason Week 3",
                    "detail": "Aug 27-Sep 5",
                }],
            }],
        }],
    }

    assert FootballEditionGenerator._week_context(payload) == {
        "season_year": 2026,
        "season_type": "1",
        "season_label": "Preseason",
        "number": 4,
        "label": "Preseason Week 3",
        "detail": "Aug 27-Sep 5",
    }


def test_football_template_is_weekly_and_highlights_today() -> None:
    template = Path("templates/football.html.j2").read_text()

    assert "{{ page.week_label }} Scoreboard &amp; Schedule" in template
    assert 'class="is-today"' in template
    assert "Today's NFL Games" not in template


def test_lead_prioritizes_eagles_then_nfc_east() -> None:
    games = FootballEditionGenerator._games({"events": [
        _event("1", "GB", "CHI"),
        _event("2", "DAL", "LV"),
        _event("3", "NYG", "PHI"),
    ]})

    lead = FootballEditionGenerator._select_lead(games)

    assert lead is not None
    assert "PHI" in lead["deck"]


def test_generator_accepts_explicit_edition_date() -> None:
    generator = FootballEditionGenerator(date(2026, 8, 20))

    assert generator.edition_date.isoformat() == "2026-08-20"


@pytest.mark.asyncio
async def test_collect_requests_and_returns_complete_espn_week(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = FootballEditionGenerator(date(2026, 8, 20))
    calls: list[tuple[str, dict[str, str]]] = []
    calendar = [{
        "value": "1",
        "entries": [{"value": "3", "label": "Preseason Week 2", "detail": "Aug 20-26"}],
    }]
    edition_payload = {
        "week": {"number": 3},
        "leagues": [{
            "season": {"year": 2026, "type": {"id": "1", "name": "Preseason"}},
            "calendar": calendar,
        }],
        "events": [_event("401", "NYG", "PHI")],
    }
    weekly_payload = {
        **edition_payload,
        "events": [_event("401", "NYG", "PHI"), _event("402", "DAL", "WAS", False)],
    }

    async def fake_get(
        _client: httpx.AsyncClient, url: str, params: dict[str, str]
    ) -> dict:
        calls.append((url, params))
        if url == "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard":
            return weekly_payload if params.get("week") else edition_payload
        return {}

    async def empty_optional(*_args: object, **_kwargs: object) -> dict:
        return {}

    monkeypatch.setattr(generator, "_get", fake_get)
    monkeypatch.setattr(generator, "_get_optional", empty_optional)

    page = await generator.collect()

    assert ("https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard", {
        "dates": "2026", "seasontype": "1", "week": "3"
    }) in calls
    assert page["week_label"] == "Preseason Week 2"
    assert page["week_detail"] == "Aug 20-26"
    assert [game["id"] for game in page["scoreboard"]] == ["401", "402"]


def test_parses_nfl_league_leaders_in_display_order() -> None:
    def category(name: str, label: str, player: str, team: str, value: str) -> dict:
        return {
            "name": name,
            "displayName": label,
            "abbreviation": "YDS",
            "leaders": [
                {
                    "displayValue": value,
                    "athlete": {
                        "displayName": player,
                        "position": {"abbreviation": "QB"},
                        "links": [
                            {
                                "rel": ["playercard", "desktop"],
                                "href": "https://www.espn.com/nfl/player/example",
                            }
                        ],
                    },
                    "team": {"abbreviation": team},
                }
            ],
        }

    payload = {
        "leaders": {
            "categories": [
                category("sacks", "Sacks", "Defender", "PHI", "18"),
                category("passingYards", "Passing Yards", "Quarterback", "BUF", "4,500"),
                category("rushingYards", "Rushing Yards", "Runner", "BAL", "1,500"),
            ]
        }
    }

    leaders = FootballEditionGenerator._league_leaders(payload)

    assert [item["name"] for item in leaders] == ["passingYards", "rushingYards", "sacks"]
    assert leaders[0]["rows"][0] == {
        "rank": 1,
        "name": "Quarterback",
        "position": "QB",
        "team": "BUF",
        "value": "4,500",
    }


def test_selects_first_full_nfl_news_article_and_skips_media() -> None:
    payload = {
        "articles": [
            {
                "id": 1,
                "type": "Media",
                "headline": "Video clip",
                "links": {"api": {"self": {"href": "https://content.core.api.espn.com/v1/video/1"}}},
            },
            {
                "id": 2,
                "type": "HeadlineNews",
                "headline": "NFL roster news",
                "description": "A complete news development.",
                "links": {"api": {"self": {"href": "https://content.core.api.espn.com/v1/sports/news/2"}}},
            },
        ]
    }

    assert FootballEditionGenerator._select_news_lead(payload) == {
        "id": "2",
        "headline": "NFL roster news",
        "description": "A complete news development.",
        "api_url": "https://content.core.api.espn.com/v1/sports/news/2",
    }


def test_nfl_league_leaders_limit_each_category_to_five() -> None:
    payload = {
        "leaders": {
            "categories": [
                {
                    "name": "passingYards",
                    "displayName": "Passing Yards",
                    "abbreviation": "YDS",
                    "leaders": [
                        {
                            "displayValue": str(5000 - rank),
                            "athlete": {"displayName": f"Player {rank}"},
                            "team": {"abbreviation": "PHI"},
                        }
                        for rank in range(1, 8)
                    ],
                }
            ]
        }
    }

    leaders = FootballEditionGenerator._league_leaders(payload)

    assert len(leaders[0]["rows"]) == 5
    assert [row["rank"] for row in leaders[0]["rows"]] == [1, 2, 3, 4, 5]


def test_nfl_leaders_season_label() -> None:
    payload = {"requestedSeason": {"year": 2026, "type": {"name": "Preseason"}}}

    assert FootballEditionGenerator._leaders_season_label(payload) == "2026 Preseason"


@pytest.mark.asyncio
async def test_football_lead_reuses_daily_cache_without_api_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = FootballEditionGenerator._games({"events": [_event("401", "NYG", "PHI")]})[0]
    service = FootballLeadStoryService(api_key="unused", cache_dir=tmp_path)
    cached = {
        "headline": "Cached Eagles Lead",
        "deck": "The published copy stays put.",
        "paragraphs": ["One.", "Two.", "Three."],
        "ai_generated": True,
        "espn_game_id": "401",
        "edition_date": "2026-08-20",
    }
    service._save_cached(game, "2026-08-20", cached)

    async def should_not_fetch(_game_id: str) -> str | None:
        raise AssertionError("ESPN and OpenAI must not be called for a cached NFL lead")

    monkeypatch.setattr(service, "_fetch_recap", should_not_fetch)
    result = await service.generate(game, "2026-08-20")

    assert result == cached
    assert service.cache_path(game, "2026-08-20").name == "nfl-2026-08-20-401.json"


@pytest.mark.asyncio
async def test_football_lead_rewrites_collected_facts_when_article_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    game = FootballEditionGenerator._games({"events": [_event("401", "NYG", "PHI")]})[0]
    service = FootballLeadStoryService(api_key="unused", cache_dir=tmp_path)
    rewritten = {
        "headline": "Facts become a full lead",
        "deck": "A grounded deck.",
        "paragraphs": ["One.", "Two.", "Three."],
        "ai_generated": True,
        "espn_game_id": "401",
        "edition_date": "2026-08-20",
    }

    async def rewrite(source: str, selected_game: dict, edition_date: str) -> dict:
        assert "Philadelphia" in source
        assert selected_game == game
        assert edition_date == "2026-08-20"
        return rewritten

    monkeypatch.setattr(service, "_rewrite", rewrite)
    result = await service.generate_from_game_facts(
        game, "2026-08-20", "Philadelphia collected game facts"
    )

    assert result == rewritten
    assert service.cache_path(game, "2026-08-20").exists()


@pytest.mark.asyncio
async def test_football_lead_rewrites_full_news_article_and_caches_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    article = {
        "id": "49802956",
        "headline": "Players prepare for season opener",
        "description": "Two veterans advanced in their injury recovery.",
        "api_url": "https://content.core.api.espn.com/v1/sports/news/49802956",
    }
    service = FootballLeadStoryService(api_key="unused", cache_dir=tmp_path)
    rewritten = {
        "headline": "Veterans Near Return",
        "deck": "Two players took another step toward the opener.",
        "paragraphs": ["One.", "Two.", "Three.", "Four."],
        "ai_generated": True,
        "espn_news_id": "49802956",
        "source_kind": "nfl_news",
        "edition_date": "2026-09-02",
    }

    async def fetch(api_url: str) -> str:
        assert api_url == article["api_url"]
        return "Grounded source article text " * 20

    async def rewrite(source: str, selected: dict, edition_date: str) -> dict:
        assert source.startswith("Grounded source")
        assert selected == article
        assert edition_date == "2026-09-02"
        return rewritten

    monkeypatch.setattr(service, "_fetch_news_article", fetch)
    monkeypatch.setattr(service, "_rewrite_news", rewrite)

    assert await service.generate_from_news(article, "2026-09-02") == rewritten
    assert service.news_cache_path(article, "2026-09-02").exists()


@pytest.mark.asyncio
async def test_around_the_nfl_rewrites_full_article_and_reuses_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    article = {
        "id": "49802956",
        "headline": "Players prepare for opener",
        "description": "Veterans advanced in their recovery.",
        "api_url": "https://content.core.api.espn.com/v1/sports/news/49802956",
    }
    service = FootballLeadStoryService(api_key="unused", cache_dir=tmp_path)

    async def fetch(_api_url: str) -> str:
        return "Grounded NFL source article text " * 20

    async def rewrite(_source: str, _article: dict) -> dict:
        return {
            "headline": "Veterans Near Return",
            "deck": "Two players moved closer to the opener.",
            "paragraphs": ["The veterans took another step in their recovery."],
            "ai_generated": True,
            "espn_news_id": "49802956",
        }

    monkeypatch.setattr(service, "_fetch_news_article", fetch)
    monkeypatch.setattr(service, "_rewrite_news_brief", rewrite)

    first = await service.generate_news_brief(article)
    assert first is not None
    assert service.news_brief_cache_path(article).exists()

    async def should_not_fetch(_api_url: str) -> str:
        raise AssertionError("ESPN must not be fetched for a cached NFL brief")

    monkeypatch.setattr(service, "_fetch_news_article", should_not_fetch)
    assert await service.generate_news_brief(article) == first


@pytest.mark.asyncio
async def test_missing_news_rewrite_publishes_empty_lead(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class EmptyNewsService:
        async def generate_from_news(self, _article: dict, _edition_date: str) -> None:
            return None

        async def generate_news_brief(self, _article: dict) -> None:
            return None

    generator = FootballEditionGenerator(
        date(2026, 9, 2), lead_story_service=EmptyNewsService()  # type: ignore[arg-type]
    )
    edition_payload = {
        "week": {"number": 1},
        "leagues": [{"season": {"year": 2026, "type": {"id": "2", "name": "Regular Season"}}}],
        "events": [],
    }
    news_payload = {
        "articles": [{
            "id": 2,
            "type": "HeadlineNews",
            "headline": "NFL roster news",
            "description": "A development.",
            "links": {"api": {"self": {"href": "https://content.core.api.espn.com/v1/sports/news/2"}}},
        }]
    }

    async def fake_get(
        _client: httpx.AsyncClient, url: str, _params: dict[str, str]
    ) -> dict:
        if url.endswith("/news"):
            return news_payload
        return edition_payload

    async def empty_optional(*_args: object, **_kwargs: object) -> dict:
        return {}

    monkeypatch.setattr(generator, "_get", fake_get)
    monkeypatch.setattr(generator, "_get_optional", empty_optional)

    page = await generator.collect()

    assert page["lead"] is None


@pytest.mark.asyncio
async def test_optional_nfl_data_failure_degrades_to_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    generator = FootballEditionGenerator(date(2026, 8, 20))

    async def fail(*_args: object, **_kwargs: object) -> dict:
        raise httpx.ConnectError("ESPN unavailable")

    monkeypatch.setattr(generator, "_get", fail)

    async with httpx.AsyncClient() as client:
        assert await generator._get_optional(client, "https://example.com", {}) == {}

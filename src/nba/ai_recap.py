from __future__ import annotations

from src.football.ai_recap import FootballLeadStoryService


class NBALeadStoryService(FootballLeadStoryService):
    """Cache original NBA leads grounded in AP-credited ESPN articles only."""

    sport_label = "NBA"
    cache_prefix = "nba"
    source_kind = "nba_news"
    summary_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary"
    schema_prefix = "nba"

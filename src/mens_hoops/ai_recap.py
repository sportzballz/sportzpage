from __future__ import annotations

from src.football.ai_recap import FootballLeadStoryService


class MensHoopsLeadStoryService(FootballLeadStoryService):
    """Cache original men's hoops leads grounded in AP-credited ESPN articles only."""

    sport_label = "NCAA Men's Basketball"
    cache_prefix = "mens-hoops"
    source_kind = "mens_hoops_news"
    summary_url = "https://site.api.espn.com/apis/site/v2/sports/basketball/mens-college-basketball/summary"
    schema_prefix = "mens_hoops"

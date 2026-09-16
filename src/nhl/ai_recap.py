from __future__ import annotations

from src.football.ai_recap import FootballLeadStoryService


class NHLLeadStoryService(FootballLeadStoryService):
    """Cache original NHL leads grounded in AP-credited ESPN articles only."""

    sport_label = "NHL"
    cache_prefix = "nhl"
    source_kind = "nhl_news"
    summary_url = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary"
    schema_prefix = "nhl"

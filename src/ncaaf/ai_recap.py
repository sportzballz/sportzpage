from __future__ import annotations

from src.football.ai_recap import FootballLeadStoryService


class NCAAFLeadStoryService(FootballLeadStoryService):
    """Create and cache ESPN-grounded college-football lead stories."""

    sport_label = "college football"
    cache_prefix = "ncaaf"
    source_kind = "ncaaf_news"
    summary_url = (
        "https://site.api.espn.com/apis/site/v2/sports/football/college-football/summary"
    )
    schema_prefix = "ncaaf"

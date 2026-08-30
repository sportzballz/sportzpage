from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Market:
    slug: str
    label: str
    baseball_teams: tuple[str, ...]
    football_teams: tuple[str, ...]


MARKETS: tuple[Market, ...] = (
    Market("philadelphia", "Philadelphia", ("PHI",), ("PHI",)),
    Market("boston", "Boston", ("BOS",), ("NE",)),
    Market("new-york", "New York", ("NYY", "NYM"), ("NYG", "NYJ")),
    Market("los-angeles", "Los Angeles", ("LAD", "LAA"), ("LAR", "LAC")),
    Market("chicago", "Chicago", ("CHC", "CWS"), ("CHI",)),
)

MARKETS_BY_SLUG = {market.slug: market for market in MARKETS}
DEFAULT_MARKET = MARKETS_BY_SLUG["philadelphia"]

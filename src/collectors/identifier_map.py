# src/collectors/identifier_map.py
from __future__ import annotations
import logging
from pathlib import Path
from typing import Any
import yaml

logger = logging.getLogger(__name__)


class TeamIdentifierMap:
    """Maps MLB Stats API team IDs and abbreviations to canonical internal values."""

    def __init__(self, teams_config_path: Path = Path("config/teams.yaml")) -> None:
        self._by_id: dict[int, dict[str, Any]] = {}
        self._by_abbr: dict[str, dict[str, Any]] = {}
        self._load(teams_config_path)

    def _load(self, path: Path) -> None:
        if not path.exists():
            logger.warning("teams.yaml not found at %s — team mapping disabled", path)
            return
        raw = yaml.safe_load(path.read_text()) or {}
        for team in raw.get("teams", []):
            self._by_id[team["team_id"]] = team
            self._by_abbr[team["abbr"]] = team

    def canonical_abbr(self, team_id: int) -> str | None:
        team = self._by_id.get(team_id)
        return team["abbr"] if team else None

    def canonical_id(self, abbr: str) -> int | None:
        team = self._by_abbr.get(abbr.upper())
        return team["team_id"] if team else None

    def is_large_market(self, abbr: str) -> bool:
        team = self._by_abbr.get(abbr.upper())
        return team.get("market") == "large" if team else False

    def get_team(self, team_id: int) -> dict[str, Any] | None:
        return self._by_id.get(team_id)

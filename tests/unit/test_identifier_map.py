# tests/unit/test_identifier_map.py
import logging
from pathlib import Path

import pytest
import yaml

from src.collectors.identifier_map import TeamIdentifierMap


TEAMS_YAML_CONTENT = {
    "teams": [
        {"team_id": 147, "abbr": "NYY", "name": "New York Yankees", "market": "large"},
        {"team_id": 111, "abbr": "BOS", "name": "Boston Red Sox", "market": "large"},
        {"team_id": 158, "abbr": "MIL", "name": "Milwaukee Brewers", "market": "small"},
        {"team_id": 134, "abbr": "PIT", "name": "Pittsburgh Pirates", "market": "small"},
    ]
}


@pytest.fixture()
def teams_yaml(tmp_path: Path) -> Path:
    path = tmp_path / "teams.yaml"
    path.write_text(yaml.dump(TEAMS_YAML_CONTENT))
    return path


class TestCanonicalAbbr:
    def test_known_team_id_returns_correct_abbr(self, teams_yaml: Path) -> None:
        m = TeamIdentifierMap(teams_yaml)
        assert m.canonical_abbr(147) == "NYY"

    def test_another_known_team_id(self, teams_yaml: Path) -> None:
        m = TeamIdentifierMap(teams_yaml)
        assert m.canonical_abbr(111) == "BOS"

    def test_unknown_team_id_returns_none(self, teams_yaml: Path) -> None:
        m = TeamIdentifierMap(teams_yaml)
        assert m.canonical_abbr(9999) is None


class TestCanonicalId:
    def test_known_abbr_returns_correct_id(self, teams_yaml: Path) -> None:
        m = TeamIdentifierMap(teams_yaml)
        assert m.canonical_id("NYY") == 147

    def test_lowercase_abbr_is_normalised(self, teams_yaml: Path) -> None:
        m = TeamIdentifierMap(teams_yaml)
        assert m.canonical_id("nyy") == 147

    def test_unknown_abbr_returns_none(self, teams_yaml: Path) -> None:
        m = TeamIdentifierMap(teams_yaml)
        assert m.canonical_id("XYZ") is None


class TestIsLargeMarket:
    def test_nyy_is_large_market(self, teams_yaml: Path) -> None:
        m = TeamIdentifierMap(teams_yaml)
        assert m.is_large_market("NYY") is True

    def test_mil_is_not_large_market(self, teams_yaml: Path) -> None:
        m = TeamIdentifierMap(teams_yaml)
        assert m.is_large_market("MIL") is False

    def test_pit_is_not_large_market(self, teams_yaml: Path) -> None:
        m = TeamIdentifierMap(teams_yaml)
        assert m.is_large_market("PIT") is False

    def test_unknown_team_is_not_large_market(self, teams_yaml: Path) -> None:
        m = TeamIdentifierMap(teams_yaml)
        assert m.is_large_market("XYZ") is False


class TestMissingFile:
    def test_missing_file_logs_warning_and_does_not_crash(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        nonexistent = tmp_path / "no_such_file.yaml"
        with caplog.at_level(logging.WARNING, logger="src.collectors.identifier_map"):
            m = TeamIdentifierMap(nonexistent)
        assert "team mapping disabled" in caplog.text
        # Maps must be empty — no crash
        assert m.canonical_abbr(147) is None
        assert m.canonical_id("NYY") is None
        assert m.is_large_market("NYY") is False


class TestGetTeam:
    def test_get_team_returns_full_dict(self, teams_yaml: Path) -> None:
        m = TeamIdentifierMap(teams_yaml)
        team = m.get_team(147)
        assert team is not None
        assert team["abbr"] == "NYY"
        assert team["name"] == "New York Yankees"

    def test_get_team_unknown_id_returns_none(self, teams_yaml: Path) -> None:
        m = TeamIdentifierMap(teams_yaml)
        assert m.get_team(0) is None

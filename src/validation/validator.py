# src/validation/validator.py
from __future__ import annotations
import difflib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from src.models.edition import Edition
from src.models.story import Story, GameRecap

logger = logging.getLogger(__name__)

FORBIDDEN_PHRASES = [
    "according to sources",
    "reportedly considering",
    "is expected to sign",
    "sources say",
    "per sources",
    "league sources indicate",
]


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def summary(self) -> str:
        return f"{len(self.errors)} errors, {len(self.warnings)} warnings"


class ContentValidator:
    """Validates Edition JSON for schema correctness and content integrity."""

    # Similarity threshold for duplicate-text detection (0.0-1.0)
    DUPLICATE_THRESHOLD = 0.85

    def validate_edition_file(self, path: Path) -> ValidationReport:
        report = ValidationReport()
        try:
            raw = json.loads(path.read_text())
        except Exception as exc:
            report.errors.append(f"Cannot parse JSON: {exc}")
            return report
        try:
            edition = Edition.model_validate(raw)
        except Exception as exc:
            report.errors.append(f"Schema validation failed: {exc}")
            return report
        self._validate_content_rules(edition, report)
        return report

    def validate_edition(self, edition: Edition) -> ValidationReport:
        report = ValidationReport()
        self._validate_content_rules(edition, report)
        return report

    def _validate_content_rules(self, edition: Edition, report: ValidationReport) -> None:
        # Collect all stories for cross-checks
        all_stories: list[Story] = []
        if edition.lead_story:
            all_stories.append(edition.lead_story)
        all_stories.extend(edition.secondary_stories)
        all_stories.extend(edition.game_recaps)
        all_stories.extend(edition.around_the_league)

        # Required field validation
        for story in all_stories:
            if not story.headline.strip():
                report.errors.append(f"Story has empty headline: type={story.story_type}")
            if not story.paragraphs or not any(p.strip() for p in story.paragraphs):
                report.errors.append(f"Story '{story.headline}' has empty body paragraphs")

        # Score validation for recaps
        for recap in edition.game_recaps:
            self._check_recap_facts(recap, edition, report)

        # Injury return date validation
        for injury in edition.injuries:
            if injury.expected_return and injury.confidence_level.value == "speculative":
                report.warnings.append(
                    f"Injury for {injury.player_name}: speculative expected_return '{injury.expected_return}' — verify before publishing."
                )

        # Forbidden phrase detection
        for story in all_stories:
            text = " ".join(story.paragraphs).lower()
            for phrase in FORBIDDEN_PHRASES:
                if phrase in text:
                    report.errors.append(
                        f"Story '{story.headline}' contains potentially invented phrase: '{phrase}'"
                    )

        # Duplicate text detection
        self._check_duplicate_texts(all_stories, report)

    def _check_recap_facts(
        self, recap: GameRecap, edition: Edition, report: ValidationReport
    ) -> None:
        game = next((g for g in edition.games if g.game_id == recap.game_id), None)
        if game is None:
            report.errors.append(
                f"GameRecap references game_id {recap.game_id} not found in edition.games"
            )
            return

        home_runs = game.home.runs or 0
        away_runs = game.away.runs or 0
        expected_home_first = (
            f"{game.home.team_abbr} {home_runs}, {game.away.team_abbr} {away_runs}"
        )
        expected_away_first = (
            f"{game.away.team_abbr} {away_runs}, {game.home.team_abbr} {home_runs}"
        )

        if recap.final_score not in (expected_home_first, expected_away_first):
            report.errors.append(
                f"Recap game {recap.game_id}: final_score '{recap.final_score}' doesn't match "
                f"game data '{expected_home_first}'"
            )

        # Player-team relationship validation
        if recap.winning_pitcher and game.winning_pitcher:
            if recap.winning_pitcher.player_id != game.winning_pitcher.player_id:
                report.warnings.append(
                    f"Recap game {recap.game_id}: winning pitcher ID mismatch "
                    f"({recap.winning_pitcher.player_id} vs {game.winning_pitcher.player_id})"
                )

    def _check_duplicate_texts(self, stories: list[Story], report: ValidationReport) -> None:
        """Detect suspiciously similar paragraph text across stories."""
        all_paragraphs: list[tuple[str, str]] = []  # (story_headline, paragraph)
        for story in stories:
            for para in story.paragraphs:
                if len(para) > 50:  # only check non-trivial paragraphs
                    all_paragraphs.append((story.headline, para.strip()))

        for i, (headline_a, para_a) in enumerate(all_paragraphs):
            for headline_b, para_b in all_paragraphs[i + 1 :]:
                if headline_a == headline_b:
                    continue  # same story
                ratio = difflib.SequenceMatcher(None, para_a, para_b).ratio()
                if ratio >= self.DUPLICATE_THRESHOLD:
                    report.warnings.append(
                        f"Duplicate text detected between '{headline_a}' and '{headline_b}' "
                        f"(similarity: {ratio:.0%})"
                    )

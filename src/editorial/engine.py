# src/editorial/engine.py
from __future__ import annotations
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from src.models.edition import Edition, EditionMetadata, GenerationMetadata, EditionType
from src.models.story import Story, GameRecap, StoryType
from src.models.game import GameStatus
from src.normalization.normalizer import NormalizedData
from src.editorial.scoring import ScoringWeights, ScoringContext, score_game
from src.editorial.fallback import generate_fallback_recap
from src.statistics.processor import StatisticsProcessor

logger = logging.getLogger(__name__)

NATIONALLY_TELEVISED = {"ESPN", "FOX", "FS1", "TBS", "MLB Network", "TBS"}


class EditorialEngine:
    """Orchestrates editorial selection, story generation, and Edition JSON assembly."""

    def __init__(
        self,
        scoring_weights: ScoringWeights,
        manual_overrides: dict[int, float],
        suppress_story_ids: list[str],
        large_market_teams: set[str],
        secondary_story_count_min: int = 3,
        secondary_story_count_max: int = 6,
        neutrality_max_fraction: float = 0.4,
        edition_type_override: str | None = None,
        ai_client: object | None = None,
    ) -> None:
        self._weights = scoring_weights
        self._overrides = manual_overrides
        self._suppress = set(suppress_story_ids)
        self._large_market = large_market_teams
        self._sec_min = secondary_story_count_min
        self._sec_max = secondary_story_count_max
        self._neutrality_max = neutrality_max_fraction
        self._edition_type_override = edition_type_override
        self._ai_client = ai_client
        self._stats = StatisticsProcessor()

    @classmethod
    def from_config(cls, edition_type_override: str | None = None) -> "EditorialEngine":
        import yaml

        cfg_path = Path("config/editorial.yaml")
        cfg: dict = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
        weights = ScoringWeights(**cfg.get("scoring_weights", {}))
        overrides = {int(k): float(v) for k, v in cfg.get("manual_lead_overrides", {}).items()}
        suppress = cfg.get("suppress_story_ids", [])
        large_market = set(cfg.get("large_market_teams", []))
        sec = cfg.get("secondary_story_count", {})
        neutrality = cfg.get("neutrality", {}).get("max_single_team_fraction", 0.4)
        return cls(
            scoring_weights=weights,
            manual_overrides=overrides,
            suppress_story_ids=suppress,
            large_market_teams=large_market,
            secondary_story_count_min=sec.get("min", 3),
            secondary_story_count_max=sec.get("max", 6),
            neutrality_max_fraction=neutrality,
            edition_type_override=edition_type_override,
        )

    async def generate(self, normalized_path: Path) -> Edition:
        """Generate an Edition from a normalized data file."""
        raw = json.loads(normalized_path.read_text())
        normalized = NormalizedData.model_validate(raw)

        edition_type = self._derive_edition_type()
        edition_id = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H%M")

        performances = self._stats.detect_notable_performances(normalized.games)
        self._stats.apply_notable_tags_to_games(normalized.games, performances)

        scored_games = []
        for g in normalized.games:
            if g.status != GameStatus.final:
                continue
            perf = performances.get(g.game_id)
            context = ScoringContext(
                has_historic_performance=bool(set(g.tags) & {"no-hitter", "perfect-game"}),
                performance_score=perf.performance_score if perf else 0.0,
                drama_score=perf.performance_score if perf else 0.0,
                is_nationally_televised=any(n in NATIONALLY_TELEVISED for n in g.tv_broadcasts),
                is_large_market=(
                    g.home.team_abbr in self._large_market or g.away.team_abbr in self._large_market
                ),
            )
            scored_games.append((g, score_game(g, context, self._weights, self._overrides)))

        scored_games.sort(key=lambda x: x[1], reverse=True)

        lead_story: Story | None = None
        secondary_stories: list[Story] = []
        game_recaps: list[GameRecap] = []
        ai_fallbacks = 0

        for i, (game, _score) in enumerate(scored_games):
            recap = await self._generate_recap(game)
            if not recap.ai_generated:
                ai_fallbacks += 1
            game_recaps.append(recap)

            if i == 0 and lead_story is None:
                lead_story = Story(
                    headline=recap.headline,
                    deck=recap.deck,
                    byline=recap.byline,
                    paragraphs=recap.paragraphs,
                    source_data_references=recap.source_data_references,
                    story_type=StoryType.lead,
                    teams=recap.teams,
                    players=recap.players,
                    facts_used=recap.facts_used,
                    ai_generated=recap.ai_generated,
                )
            elif len(secondary_stories) < self._sec_max:
                secondary_stories.append(
                    Story(
                        headline=recap.headline,
                        deck=recap.deck,
                        byline=recap.byline,
                        paragraphs=recap.paragraphs[:1],
                        source_data_references=recap.source_data_references,
                        story_type=StoryType.secondary,
                        teams=recap.teams,
                        players=recap.players,
                        facts_used=recap.facts_used,
                        ai_generated=recap.ai_generated,
                    )
                )

        import platform

        return Edition(
            edition=EditionMetadata(
                id=edition_id,
                type=edition_type,
                date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                generated_at=datetime.now(timezone.utc),
                data_current_through=datetime.now(timezone.utc),
                status="draft",
            ),
            lead_story=lead_story,
            secondary_stories=secondary_stories,
            games=normalized.games,
            standings=normalized.standings,
            league_leaders=normalized.league_leaders,
            game_recaps=game_recaps,
            transactions=normalized.transactions,
            injuries=normalized.injuries,
            generation_metadata=GenerationMetadata(
                pipeline_version="0.1.0",
                python_version=platform.python_version(),
                ai_fallbacks=ai_fallbacks,
            ),
        )

    async def _generate_recap(self, game) -> GameRecap:
        """Generate a recap via AI, falling back to deterministic template."""
        if self._ai_client is None:
            return generate_fallback_recap(game)
        try:
            return await self._generate_ai_recap(game)
        except Exception as exc:
            logger.warning("AI recap failed for game %d, using fallback: %s", game.game_id, exc)
            return generate_fallback_recap(game)

    async def _generate_ai_recap(self, game) -> GameRecap:
        raise NotImplementedError("AI recap generation to be implemented with provider SDK.")

    def _derive_edition_type(self) -> EditionType:
        if self._edition_type_override:
            return self._edition_type_override  # type: ignore[return-value]
        hour = datetime.now(timezone.utc).hour
        if hour < 10:
            return "morning"
        if hour < 14:
            return "midday"
        if hour < 20:
            return "evening"
        if hour < 23:
            return "late"
        return "final"

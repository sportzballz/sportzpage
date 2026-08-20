# src/editorial/engine.py
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from src.editorial.fallback import generate_fallback_recap
from src.editorial.scoring import ScoringContext, ScoringWeights, score_game
from src.models.edition import Edition, EditionMetadata, EditionType, GenerationMetadata
from src.models.game import Game, GameStatus
from src.models.story import GameRecap, Story, StoryType
from src.normalization.normalizer import NormalizedData
from src.statistics.processor import StatisticsProcessor

logger = logging.getLogger(__name__)

NATIONALLY_TELEVISED = {"ESPN", "FOX", "FS1", "TBS", "MLB Network"}


def _involves_team(game: Game, team_abbr: str) -> bool:
    return game.home.team_abbr == team_abbr or game.away.team_abbr == team_abbr


def prioritize_primary_team(
    scored_games: list[tuple[Game, float]], primary_team_abbr: str
) -> list[tuple[Game, float]]:
    """Put the primary team's top completed game first without hiding MLB-wide news."""
    primary = [item for item in scored_games if _involves_team(item[0], primary_team_abbr)]
    if not primary:
        return scored_games
    lead = primary[0]
    return [lead, *(item for item in scored_games if item is not lead)]


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
        primary_team_abbr: str = "PHI",
        require_primary_team_lead: bool = True,
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
        self._primary_team = primary_team_abbr
        self._require_primary_team_lead = require_primary_team_lead
        self._edition_type_override = edition_type_override
        self._ai_client = ai_client
        self._stats = StatisticsProcessor()

    @classmethod
    def from_config(cls, edition_type_override: str | None = None) -> EditorialEngine:
        import yaml

        cfg_path = Path("config/editorial.yaml")
        cfg: dict = yaml.safe_load(cfg_path.read_text()) if cfg_path.exists() else {}
        weights = ScoringWeights(**cfg.get("scoring_weights", {}))
        overrides = {int(k): float(v) for k, v in cfg.get("manual_lead_overrides", {}).items()}
        suppress = cfg.get("suppress_story_ids", [])
        large_market = set(cfg.get("large_market_teams", []))
        sec = cfg.get("secondary_story_count", {})
        neutrality = cfg.get("neutrality", {}).get("max_single_team_fraction", 0.4)
        focus = cfg.get("editorial_focus", {})
        return cls(
            scoring_weights=weights,
            manual_overrides=overrides,
            suppress_story_ids=suppress,
            large_market_teams=large_market,
            secondary_story_count_min=sec.get("min", 3),
            secondary_story_count_max=sec.get("max", 6),
            neutrality_max_fraction=neutrality,
            primary_team_abbr=focus.get("primary_team", "PHI"),
            require_primary_team_lead=focus.get("require_primary_team_lead", True),
            edition_type_override=edition_type_override,
        )

    async def generate(self, normalized_path: Path) -> Edition:
        """Generate an Edition from a normalized data file."""
        raw = json.loads(normalized_path.read_text())
        normalized = NormalizedData.model_validate(raw)

        edition_type = self._derive_edition_type()
        edition_id = datetime.now(UTC).strftime("%Y-%m-%d-%H%M")

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
        if self._require_primary_team_lead:
            scored_games = prioritize_primary_team(scored_games, self._primary_team)

        lead_story: Story | None = None
        secondary_stories: list[Story] = []
        game_recaps: list[GameRecap] = []
        ai_fallbacks = 0

        if self._require_primary_team_lead and not any(
            _involves_team(game, self._primary_team) for game, _score in scored_games
        ):
            primary_game = next(
                (game for game in normalized.games if _involves_team(game, self._primary_team)),
                None,
            )
            lead_story = self._primary_team_fallback(primary_game)

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
                date=datetime.now(UTC).strftime("%Y-%m-%d"),
                generated_at=datetime.now(UTC),
                data_current_through=datetime.now(UTC),
                status="draft",
            ),
            lead_story=lead_story,
            secondary_stories=secondary_stories,
            games=normalized.games,
            standings=normalized.standings,
            league_leaders=normalized.league_leaders,
            game_recaps=game_recaps,
            around_the_league=normalized.news_stories,
            transactions=normalized.transactions,
            historical_items=normalized.historical_items,
            team_season_leaders=normalized.team_season_leaders,
            generation_metadata=GenerationMetadata(
                pipeline_version="0.1.0",
                python_version=platform.python_version(),
                ai_fallbacks=ai_fallbacks,
            ),
        )

    async def _generate_recap(self, game: Game) -> GameRecap:
        """Generate a recap via AI, falling back to deterministic template."""
        if self._ai_client is None:
            return generate_fallback_recap(game)
        try:
            return await self._generate_ai_recap(game)
        except Exception as exc:
            logger.warning("AI recap failed for game %d, using fallback: %s", game.game_id, exc)
            return generate_fallback_recap(game)

    async def _generate_ai_recap(self, game: Game) -> GameRecap:
        raise NotImplementedError("AI recap generation to be implemented with provider SDK.")

    def _primary_team_fallback(self, game: Game | None) -> Story:
        """Keep the front page Phillies-led on off-days or before a game is final."""
        if game is not None:
            opponent = game.away if game.home.team_abbr == self._primary_team else game.home
            time_text = game.game_time_et or "a time to be announced"
            status_text = game.status.value.replace("_", " ")
            return Story(
                headline=f"Phillies Turn Their Attention to {opponent.team_name}",
                deck=f"Philadelphia's next listed matchup is {status_text} for {time_text} ET.",
                byline="SportzBallz Staff",
                paragraphs=[
                    f"The Phillies and {opponent.team_name} are the Philadelphia focus while "
                    "The Daily Sportz Page tracks the full Major League Baseball slate."
                ],
                source_data_references=[f"game:{game.game_id}"],
                story_type=StoryType.lead,
                teams=[self._primary_team, opponent.team_abbr],
                facts_used=[f"game_id:{game.game_id}", f"status:{game.status.value}"],
                ai_generated=False,
            )
        return Story(
            headline="Phillies Remain the Focus in Philadelphia",
            deck=(
                "The Daily Sportz Page leads with the Phillies and covers the rest of "
                "Major League Baseball."
            ),
            byline="SportzBallz Staff",
            paragraphs=[
                "No Phillies game appeared in the current data window, so the front page "
                "turns to the club's next update while the full MLB report continues below."
            ],
            source_data_references=[],
            story_type=StoryType.lead,
            teams=[self._primary_team],
            facts_used=[],
            ai_generated=False,
        )

    def _derive_edition_type(self) -> EditionType:
        if self._edition_type_override:
            return self._edition_type_override  # type: ignore[return-value]
        hour = datetime.now(UTC).hour
        if hour < 10:
            return "morning"
        if hour < 14:
            return "midday"
        if hour < 20:
            return "evening"
        if hour < 23:
            return "late"
        return "final"

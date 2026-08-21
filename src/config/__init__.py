# src/config/__init__.py
from __future__ import annotations
import os
from pathlib import Path
from typing import Any, Optional, Union
import yaml
from pydantic import BaseModel, Field


class MLBApiConfig(BaseModel):
    base_url: str = "https://statsapi.mlb.com/api/v1"
    timeout_seconds: float = 10.0
    max_attempts: int = 3
    backoff_min_seconds: float = 1.0
    backoff_max_seconds: float = 30.0


class AIConfig(BaseModel):
    provider: str = "none"  # openai | anthropic | none
    model: str = "gpt-4o"
    timeout_seconds: float = 30.0
    max_retries: int = 2


class FreshnessConfig(BaseModel):
    live_scores: int = 300
    scheduled_games: int = 1800
    standings: int = 1800
    league_leaders: int = 21600
    transactions: int = 1800
    injuries: int = 7200
    historical_data: int = 2592000


class PerformanceConfig(BaseModel):
    html_max_bytes: int = 512000
    total_page_max_bytes: int = 2097152


class FeaturesConfig(BaseModel):
    archive_enabled: bool = True
    dark_mode_enabled: bool = True
    betting_content_enabled: bool = False
    image_generation_enabled: bool = False


class Settings(BaseModel):
    build_dir: str = "build"
    publish_root: str = "/var/www/sportzballz/sportzpage"
    archive_root: str = "/var/www/sportzballz/sportzpage/archive"
    last_known_good_filename: str = "index.html.lkg"
    public_base_url: str = "https://sportzballz.io/sportzpage"
    publication_name: str = "The Daily Sportz Page"
    cdn_purge_hook: Optional[str] = None
    mlb_api: MLBApiConfig = Field(default_factory=MLBApiConfig)
    ai: AIConfig = Field(default_factory=AIConfig)
    freshness_max_age_seconds: FreshnessConfig = Field(default_factory=FreshnessConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    features: FeaturesConfig = Field(default_factory=FeaturesConfig)


_cached_settings: Optional[Settings] = None


def load_settings(config_path: Optional[Union[str, Path]] = None) -> Settings:
    """Load settings from config/settings.yaml or the provided path."""
    global _cached_settings
    if _cached_settings is not None and config_path is None:
        return _cached_settings

    path = Path(config_path or "config/settings.yaml")
    if not path.exists():
        return Settings()

    raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    ai = raw.setdefault("ai", {})
    if provider := os.getenv("AI_PROVIDER"):
        ai["provider"] = provider
    if model := os.getenv("AI_MODEL"):
        ai["model"] = model
    settings = Settings.model_validate(raw)
    if config_path is None:
        _cached_settings = settings
    return settings


def reset_settings_cache() -> None:
    """Reset the settings cache (useful in tests)."""
    global _cached_settings
    _cached_settings = None

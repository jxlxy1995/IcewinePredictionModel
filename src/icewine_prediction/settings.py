from dataclasses import dataclass
import os
from pathlib import Path
from typing import Any

from dotenv import dotenv_values, find_dotenv, load_dotenv
import yaml


@dataclass(frozen=True)
class SourceSettings:
    base_url: str
    timeout_seconds: int
    daily_request_budget: int
    cache_enabled: bool


@dataclass(frozen=True)
class LeagueSettings:
    name: str
    country: str
    api_football_id: int
    enabled: bool
    priority: int


@dataclass(frozen=True)
class SyncSettings:
    default_days: int
    default_source: str
    sync_odds: bool
    sync_results: bool
    budget_guard_enabled: bool


@dataclass(frozen=True)
class ProjectSettings:
    api_football_key: str | None
    sources: dict[str, SourceSettings]
    leagues: list[LeagueSettings]
    sync: SyncSettings


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def load_project_settings(config_dir: Path = Path("config")) -> ProjectSettings:
    env_path = find_dotenv(usecwd=True)
    if env_path:
        for key, value in dotenv_values(env_path, encoding="utf-8-sig").items():
            if value is not None:
                os.environ.setdefault(key, value)
    else:
        load_dotenv()
    sources_raw = _load_yaml(config_dir / "sources.yaml")
    leagues_raw = _load_yaml(config_dir / "leagues.yaml")
    sync_raw = _load_yaml(config_dir / "sync.yaml")
    sources = {
        name: SourceSettings(
            base_url=value["base_url"],
            timeout_seconds=int(value["timeout_seconds"]),
            daily_request_budget=int(value["daily_request_budget"]),
            cache_enabled=bool(value["cache_enabled"]),
        )
        for name, value in sources_raw.items()
    }
    leagues = [
        LeagueSettings(
            name=item["name"],
            country=item["country"],
            api_football_id=int(item["api_football_id"]),
            enabled=bool(item["enabled"]),
            priority=int(item["priority"]),
        )
        for item in leagues_raw.get("leagues", [])
    ]
    sync = SyncSettings(
        default_days=int(sync_raw["default_days"]),
        default_source=sync_raw["default_source"],
        sync_odds=bool(sync_raw["sync_odds"]),
        sync_results=bool(sync_raw["sync_results"]),
        budget_guard_enabled=bool(sync_raw["budget_guard_enabled"]),
    )
    return ProjectSettings(
        api_football_key=os.getenv("API_FOOTBALL_KEY"),
        sources=sources,
        leagues=leagues,
        sync=sync,
    )

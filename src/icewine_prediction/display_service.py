from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class DisplayNames:
    leagues: dict[str, str]
    teams: dict[str, str]


def load_display_names(path: Path = Path("config/display_names.yaml")) -> DisplayNames:
    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}
    return DisplayNames(
        leagues=dict(payload.get("leagues", {})),
        teams=dict(payload.get("teams", {})),
    )


class DisplayNameService:
    def __init__(self, display_names: DisplayNames | None = None) -> None:
        self.display_names = display_names or load_display_names()

    def display_league(self, name: str) -> str:
        return self.display_names.leagues.get(name, name)

    def display_team(self, name: str) -> str:
        return self.display_names.teams.get(name, name)

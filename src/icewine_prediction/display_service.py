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


def save_team_display_names(
    team_display_names: dict[str, str],
    *,
    path: Path = Path("config/display_names.yaml"),
) -> None:
    payload = _load_display_payload(path)
    teams = dict(payload.get("teams", {}))
    teams.update(
        {
            team_name: display_name
            for team_name, display_name in team_display_names.items()
            if display_name.strip()
        }
    )
    payload["teams"] = dict(sorted(teams.items()))
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


class DisplayNameService:
    def __init__(self, display_names: DisplayNames | None = None) -> None:
        self.display_names = display_names or load_display_names()

    def display_league(self, name: str) -> str:
        return self.display_names.leagues.get(name, name)

    def display_team(self, name: str) -> str:
        return self.display_names.teams.get(name, name)


def _load_display_payload(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        payload = yaml.safe_load(file) or {}
    return dict(payload)

from pathlib import Path
from typing import Any

import yaml


DEFAULT_STATUS_PATH = Path("config/display_translation_status.yaml")


class DisplayTranslationStatusService:
    def __init__(self, path: Path = DEFAULT_STATUS_PATH) -> None:
        self.path = path

    def is_done(self, *, league_id: int, season: int) -> bool:
        return _key(league_id, season) in self.list_done_keys()

    def list_done_keys(self) -> set[str]:
        payload = self._read_payload()
        return set(payload.get("done_league_seasons", []))

    def mark_done(self, *, league_id: int, season: int) -> None:
        payload = self._read_payload()
        done_keys = set(payload.get("done_league_seasons", []))
        done_keys.add(_key(league_id, season))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            yaml.safe_dump(
                {"done_league_seasons": sorted(done_keys)},
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def _read_payload(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"done_league_seasons": []}
        payload = yaml.safe_load(self.path.read_text(encoding="utf-8")) or {}
        if not isinstance(payload, dict):
            return {"done_league_seasons": []}
        return payload


def _key(league_id: int, season: int) -> str:
    return f"{league_id}-{season}"

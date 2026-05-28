from __future__ import annotations

from dataclasses import dataclass
import json
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from icewine_prediction.alias_service import normalize_alias_name

ODDSPAPI_SOURCE_NAME = "oddspapi"
TEAM_ENTITY_TYPE = "team"


@dataclass(frozen=True)
class OddsPapiAliasSuggestion:
    canonical_name: str
    alias_name: str
    side: str
    anchor_side: str
    match_id: int
    league_name: str
    fixture_id: str
    side_similarity: Decimal
    anchor_similarity: Decimal


@dataclass(frozen=True)
class OddsPapiAliasSuggestionReport:
    report_dir: Path
    alias_config_path: Path
    suggestion_count: int
    skipped_existing_alias_count: int
    suggestions: tuple[OddsPapiAliasSuggestion, ...]


def build_oddspapi_alias_suggestions_text(
    report_dir: str | Path,
    alias_config_path: str | Path = "config/external_aliases.yaml",
    alias_threshold: Decimal | str = Decimal("0.75"),
    anchor_threshold: Decimal | str = Decimal("0.75"),
) -> str:
    report = build_oddspapi_alias_suggestions(
        report_dir=report_dir,
        alias_config_path=alias_config_path,
        alias_threshold=alias_threshold,
        anchor_threshold=anchor_threshold,
    )
    return format_oddspapi_alias_suggestions(report)


def build_oddspapi_alias_suggestions(
    report_dir: str | Path,
    alias_config_path: str | Path = "config/external_aliases.yaml",
    alias_threshold: Decimal | str = Decimal("0.75"),
    anchor_threshold: Decimal | str = Decimal("0.75"),
) -> OddsPapiAliasSuggestionReport:
    report_dir = Path(report_dir)
    alias_config_path = Path(alias_config_path)
    alias_threshold = Decimal(str(alias_threshold))
    anchor_threshold = Decimal(str(anchor_threshold))
    existing_aliases = _load_existing_alias_keys(alias_config_path)
    suggestions = []
    skipped_existing_alias_count = 0
    seen_keys = set()
    for match_payload in _load_match_payloads(report_dir / "matches.jsonl"):
        if match_payload.get("failure_category") != "team_name_mismatch":
            continue
        for candidate in match_payload.get("candidates") or []:
            for suggestion in _build_candidate_suggestions(
                match_payload=match_payload,
                candidate=candidate,
                alias_threshold=alias_threshold,
                anchor_threshold=anchor_threshold,
            ):
                alias_key = _alias_key(suggestion.canonical_name, suggestion.alias_name)
                if alias_key in existing_aliases:
                    skipped_existing_alias_count += 1
                    continue
                if alias_key in seen_keys:
                    continue
                seen_keys.add(alias_key)
                suggestions.append(suggestion)
    return OddsPapiAliasSuggestionReport(
        report_dir=report_dir,
        alias_config_path=alias_config_path,
        suggestion_count=len(suggestions),
        skipped_existing_alias_count=skipped_existing_alias_count,
        suggestions=tuple(suggestions),
    )


def format_oddspapi_alias_suggestions(report: OddsPapiAliasSuggestionReport) -> str:
    lines = [
        "OddsPapi alias suggestions",
        f"report_dir: {report.report_dir}",
        f"alias_config_path: {report.alias_config_path}",
        f"suggestions: {report.suggestion_count}",
        f"skipped_existing_aliases: {report.skipped_existing_alias_count}",
        "",
    ]
    if not report.suggestions:
        lines.append("No alias suggestions.")
        return "\n".join(lines)
    lines.append("aliases:")
    alias_payload = {
        "aliases": [
            {
                "entity_type": TEAM_ENTITY_TYPE,
                "source_name": ODDSPAPI_SOURCE_NAME,
                "canonical_name": suggestion.canonical_name,
                "alias_name": suggestion.alias_name,
            }
            for suggestion in report.suggestions
        ]
    }
    yaml_text = yaml.safe_dump(
        alias_payload,
        allow_unicode=True,
        sort_keys=False,
    )
    lines.extend(yaml_text.splitlines()[1:])
    lines.extend(["", "evidence:"])
    for suggestion in report.suggestions:
        lines.append(
            "- "
            f"match_id={suggestion.match_id} league={suggestion.league_name} "
            f"fixture={suggestion.fixture_id} side={suggestion.side} "
            f"alias={suggestion.alias_name} anchor={suggestion.anchor_side} "
            f"side_similarity={suggestion.side_similarity} "
            f"anchor_similarity={suggestion.anchor_similarity}"
        )
    return "\n".join(lines)


def _build_candidate_suggestions(
    match_payload: dict[str, Any],
    candidate: dict[str, Any],
    alias_threshold: Decimal,
    anchor_threshold: Decimal,
) -> list[OddsPapiAliasSuggestion]:
    home_similarity = Decimal(str(candidate.get("home_similarity", "0")))
    away_similarity = Decimal(str(candidate.get("away_similarity", "0")))
    suggestions = []
    if home_similarity < alias_threshold and away_similarity >= anchor_threshold:
        suggestions.append(
            _build_suggestion(
                match_payload=match_payload,
                candidate=candidate,
                side="home",
                anchor_side="away",
                side_similarity=home_similarity,
                anchor_similarity=away_similarity,
            )
        )
    if away_similarity < alias_threshold and home_similarity >= anchor_threshold:
        suggestions.append(
            _build_suggestion(
                match_payload=match_payload,
                candidate=candidate,
                side="away",
                anchor_side="home",
                side_similarity=away_similarity,
                anchor_similarity=home_similarity,
            )
        )
    return [
        suggestion
        for suggestion in suggestions
        if normalize_alias_name(suggestion.canonical_name)
        != normalize_alias_name(suggestion.alias_name)
    ]


def _build_suggestion(
    match_payload: dict[str, Any],
    candidate: dict[str, Any],
    side: str,
    anchor_side: str,
    side_similarity: Decimal,
    anchor_similarity: Decimal,
) -> OddsPapiAliasSuggestion:
    return OddsPapiAliasSuggestion(
        canonical_name=str(match_payload[f"{side}_team_name"]),
        alias_name=str(candidate[f"{side}_team_name"]),
        side=side,
        anchor_side=anchor_side,
        match_id=int(match_payload["match_id"]),
        league_name=str(match_payload.get("league_name") or ""),
        fixture_id=str(candidate.get("fixture_id") or ""),
        side_similarity=side_similarity,
        anchor_similarity=anchor_similarity,
    )


def _load_match_payloads(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"diagnostic matches file not found: {path}")
    payloads = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            payloads.append(json.loads(line))
    return payloads


def _load_existing_alias_keys(path: Path) -> set[tuple[str, str]]:
    if not path.exists():
        return set()
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    keys = set()
    for item in payload.get("aliases", []):
        if item.get("entity_type") != TEAM_ENTITY_TYPE:
            continue
        if item.get("source_name") != ODDSPAPI_SOURCE_NAME:
            continue
        canonical_name = item.get("canonical_name")
        alias_name = item.get("alias_name")
        if not canonical_name or not alias_name:
            continue
        keys.add(_alias_key(str(canonical_name), str(alias_name)))
    return keys


def _alias_key(canonical_name: str, alias_name: str) -> tuple[str, str]:
    return (canonical_name, normalize_alias_name(alias_name))

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from icewine_prediction.models import Match
from icewine_prediction.odds_source_match_service import (
    ExternalAliasInput,
    OddsPapiFixture,
    _best_team_name_similarity,
)
from icewine_prediction.oddspapi_sync_runner import (
    API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS,
    ODDSPAPI_BASE_URL,
    OddsPapiSyncClient,
    _build_fixture_cache_key,
    _load_team_aliases,
    _open_session,
    select_oddspapi_candidate_matches,
)
from icewine_prediction.settings import load_project_settings
from icewine_prediction.sources.oddspapi_client import (
    OddsPapiApiError,
    OddsPapiClient,
    OddsPapiRequestBudgetExceededError,
)
from icewine_prediction.time_utils import now_beijing

UTC_TIMEZONE = ZoneInfo("UTC")
BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")


@dataclass(frozen=True)
class OddsPapiFixtureDiagnosticCandidate:
    fixture_id: str
    tournament_id: int
    start_time_utc: str
    home_team_name: str
    away_team_name: str
    time_delta_seconds: int
    home_similarity: Decimal
    away_similarity: Decimal
    confidence: Decimal
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "fixture_id": self.fixture_id,
            "tournament_id": self.tournament_id,
            "start_time_utc": self.start_time_utc,
            "home_team_name": self.home_team_name,
            "away_team_name": self.away_team_name,
            "time_delta_seconds": self.time_delta_seconds,
            "home_similarity": str(self.home_similarity),
            "away_similarity": str(self.away_similarity),
            "confidence": str(self.confidence),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class OddsPapiFixtureDiagnosticMatch:
    match_id: int
    league_name: str
    source_league_id: str | None
    expected_tournament_id: int | None
    kickoff_time_beijing: str
    kickoff_time_utc: str
    home_team_name: str
    away_team_name: str
    status: str
    reason: str
    candidate_count: int
    best_fixture_id: str | None
    best_confidence: Decimal | None
    candidates: tuple[OddsPapiFixtureDiagnosticCandidate, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "match_id": self.match_id,
            "league_name": self.league_name,
            "source_league_id": self.source_league_id,
            "expected_tournament_id": self.expected_tournament_id,
            "kickoff_time_beijing": self.kickoff_time_beijing,
            "kickoff_time_utc": self.kickoff_time_utc,
            "home_team_name": self.home_team_name,
            "away_team_name": self.away_team_name,
            "status": self.status,
            "reason": self.reason,
            "candidate_count": self.candidate_count,
            "best_fixture_id": self.best_fixture_id,
            "best_confidence": str(self.best_confidence) if self.best_confidence is not None else None,
            "candidates": [candidate.to_dict() for candidate in self.candidates],
        }


@dataclass(frozen=True)
class OddsPapiFixtureDiagnosticReport:
    run_id: str
    report_dir: Path
    season: int
    diagnosed_match_count: int
    matched_count: int
    manual_review_count: int
    no_candidate_count: int
    missing_mapping_count: int
    api_error_count: int
    skipped_existing_odds_count: int
    requests_used: int
    matches: tuple[OddsPapiFixtureDiagnosticMatch, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "report_dir": str(self.report_dir),
            "season": self.season,
            "diagnosed_match_count": self.diagnosed_match_count,
            "matched_count": self.matched_count,
            "manual_review_count": self.manual_review_count,
            "no_candidate_count": self.no_candidate_count,
            "missing_mapping_count": self.missing_mapping_count,
            "api_error_count": self.api_error_count,
            "skipped_existing_odds_count": self.skipped_existing_odds_count,
            "requests_used": self.requests_used,
        }


def run_oddspapi_fixture_diagnostics(
    season: int,
    max_matches: int,
    request_budget: int,
    timeout_seconds: int = 20,
    log_dir: str | Path = "logs/odds-diagnostics",
    league_ids: set[str] | None = None,
    from_date: date | datetime | None = None,
    confidence_threshold: Decimal | str = Decimal("0.75"),
) -> str:
    settings = load_project_settings()
    raw_client = OddsPapiClient(
        base_url=ODDSPAPI_BASE_URL,
        api_key=settings.odds_papi_key,
        timeout_seconds=timeout_seconds,
        request_budget=request_budget,
    )
    client = OddsPapiSyncClient(raw_client)
    with _open_session() as session:
        report = run_oddspapi_fixture_diagnostics_for_session(
            session=session,
            client=client,
            season=season,
            max_matches=max_matches,
            request_budget=request_budget,
            log_dir=log_dir,
            league_ids=league_ids,
            from_date=from_date,
            confidence_threshold=confidence_threshold,
        )
    return format_oddspapi_fixture_diagnostic_report(report)


def run_oddspapi_fixture_diagnostics_for_session(
    session: Session,
    client: OddsPapiSyncClient,
    season: int,
    max_matches: int,
    request_budget: int,
    log_dir: str | Path,
    run_id: str | None = None,
    league_ids: set[str] | None = None,
    from_date: date | datetime | None = None,
    confidence_threshold: Decimal | str = Decimal("0.75"),
) -> OddsPapiFixtureDiagnosticReport:
    threshold = Decimal(str(confidence_threshold))
    run_id = run_id or build_oddspapi_fixture_diagnostic_run_id()
    report_dir = Path(log_dir) / run_id
    matches, skipped_existing_odds = select_oddspapi_candidate_matches(
        session=session,
        season=season,
        max_matches=max_matches,
        league_ids=league_ids,
        from_date=from_date,
    )
    team_aliases = _load_team_aliases(session)
    fixture_cache: dict[tuple[int, str, str], list[OddsPapiFixture]] = {}
    diagnostic_matches = []
    for match in matches:
        if client.request_count >= request_budget:
            diagnostic_matches.append(
                _build_api_error_match(match, "request budget exhausted before fixture fetch")
            )
            break
        diagnostic_matches.append(
            _diagnose_match(
                match=match,
                client=client,
                fixture_cache=fixture_cache,
                team_aliases=team_aliases,
                confidence_threshold=threshold,
            )
        )
    report = _build_report(
        run_id=run_id,
        report_dir=report_dir,
        season=season,
        skipped_existing_odds=skipped_existing_odds,
        requests_used=client.request_count,
        matches=tuple(diagnostic_matches),
    )
    write_oddspapi_fixture_diagnostic_report(report)
    return report


def build_oddspapi_fixture_diagnostic_run_id(current_time: datetime | None = None) -> str:
    current_time = current_time or now_beijing()
    return current_time.strftime("%Y%m%d-%H%M%S-%f-oddspapi-fixture-diagnostic")


def write_oddspapi_fixture_diagnostic_report(
    report: OddsPapiFixtureDiagnosticReport,
) -> None:
    report.report_dir.mkdir(parents=True, exist_ok=True)
    (report.report_dir / "run.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (report.report_dir / "matches.jsonl").open("w", encoding="utf-8") as file:
        for match in report.matches:
            file.write(json.dumps(match.to_dict(), ensure_ascii=False) + "\n")
    _write_manual_review_csv(report)
    (report.report_dir / "summary.md").write_text(
        _format_summary_markdown(report),
        encoding="utf-8",
    )


def format_oddspapi_fixture_diagnostic_report(
    report: OddsPapiFixtureDiagnosticReport,
) -> str:
    return "\n".join(
        [
            "OddsPapi fixture diagnostic completed",
            f"run_id: {report.run_id}",
            f"report_dir: {report.report_dir}",
            f"diagnosed: {report.diagnosed_match_count}",
            f"matched: {report.matched_count}",
            f"manual_review: {report.manual_review_count}",
            f"no_candidate: {report.no_candidate_count}",
            f"api_error: {report.api_error_count}",
            f"requests_used: {report.requests_used}",
        ]
    )


def _diagnose_match(
    match: Match,
    client: OddsPapiSyncClient,
    fixture_cache: dict[tuple[int, str, str], list[OddsPapiFixture]],
    team_aliases: list[ExternalAliasInput],
    confidence_threshold: Decimal,
) -> OddsPapiFixtureDiagnosticMatch:
    tournament_id = API_FOOTBALL_TO_ODDSPAPI_TOURNAMENT_IDS.get(str(match.league.source_league_id))
    if tournament_id is None:
        return _build_empty_match(
            match=match,
            expected_tournament_id=None,
            status="missing_tournament_mapping",
            reason="API-Football league is not mapped to OddsPapi tournament",
        )
    try:
        cache_key = _build_fixture_cache_key(tournament_id, match.kickoff_time)
        if cache_key not in fixture_cache:
            fixture_cache[cache_key] = client.fetch_fixtures(
                tournament_id=tournament_id,
                kickoff_time=match.kickoff_time,
            )
        fixtures = fixture_cache[cache_key]
    except (OddsPapiApiError, OddsPapiRequestBudgetExceededError) as exc:
        return _build_api_error_match(match, str(exc), expected_tournament_id=tournament_id)
    candidates = tuple(
        sorted(
            (
                _build_candidate(
                    match=match,
                    fixture=fixture,
                    team_aliases=team_aliases,
                )
                for fixture in fixtures
            ),
            key=lambda candidate: (-candidate.confidence, candidate.time_delta_seconds),
        )
    )
    if not candidates:
        return _build_empty_match(
            match=match,
            expected_tournament_id=tournament_id,
            status="no_candidate",
            reason="OddsPapi returned no fixture candidates in the UTC window",
        )
    best = candidates[0]
    if best.confidence >= confidence_threshold:
        status = "matched"
        reason = "best candidate meets team similarity threshold"
    else:
        status = "manual_review"
        reason = "team similarity below threshold; inspect candidates and aliases"
    return _build_match(
        match=match,
        expected_tournament_id=tournament_id,
        status=status,
        reason=reason,
        candidates=candidates,
        best_fixture_id=best.fixture_id,
        best_confidence=best.confidence,
    )


def _build_candidate(
    match: Match,
    fixture: OddsPapiFixture,
    team_aliases: list[ExternalAliasInput],
) -> OddsPapiFixtureDiagnosticCandidate:
    home_similarity = _best_team_name_similarity(
        match.home_team.canonical_name,
        fixture.home_team_name,
        team_aliases,
    )
    away_similarity = _best_team_name_similarity(
        match.away_team.canonical_name,
        fixture.away_team_name,
        team_aliases,
    )
    time_delta_seconds = int(
        abs((_as_utc(match.kickoff_time, BEIJING_TIMEZONE) - _as_utc(fixture.start_time, UTC_TIMEZONE)).total_seconds())
    )
    confidence = min(home_similarity, away_similarity)
    reason = (
        f"home_similarity={home_similarity}; away_similarity={away_similarity}; "
        f"time_delta_seconds={time_delta_seconds}"
    )
    return OddsPapiFixtureDiagnosticCandidate(
        fixture_id=fixture.fixture_id,
        tournament_id=fixture.tournament_id,
        start_time_utc=_format_utc(fixture.start_time),
        home_team_name=fixture.home_team_name,
        away_team_name=fixture.away_team_name,
        time_delta_seconds=time_delta_seconds,
        home_similarity=home_similarity,
        away_similarity=away_similarity,
        confidence=confidence,
        reason=reason,
    )


def _build_report(
    run_id: str,
    report_dir: Path,
    season: int,
    skipped_existing_odds: int,
    requests_used: int,
    matches: tuple[OddsPapiFixtureDiagnosticMatch, ...],
) -> OddsPapiFixtureDiagnosticReport:
    return OddsPapiFixtureDiagnosticReport(
        run_id=run_id,
        report_dir=report_dir,
        season=season,
        diagnosed_match_count=len(matches),
        matched_count=_count_status(matches, "matched"),
        manual_review_count=_count_status(matches, "manual_review"),
        no_candidate_count=_count_status(matches, "no_candidate"),
        missing_mapping_count=_count_status(matches, "missing_tournament_mapping"),
        api_error_count=_count_status(matches, "api_error"),
        skipped_existing_odds_count=skipped_existing_odds,
        requests_used=requests_used,
        matches=matches,
    )


def _build_empty_match(
    match: Match,
    expected_tournament_id: int | None,
    status: str,
    reason: str,
) -> OddsPapiFixtureDiagnosticMatch:
    return _build_match(
        match=match,
        expected_tournament_id=expected_tournament_id,
        status=status,
        reason=reason,
        candidates=(),
        best_fixture_id=None,
        best_confidence=None,
    )


def _build_api_error_match(
    match: Match,
    reason: str,
    expected_tournament_id: int | None = None,
) -> OddsPapiFixtureDiagnosticMatch:
    return _build_empty_match(
        match=match,
        expected_tournament_id=expected_tournament_id,
        status="api_error",
        reason=reason,
    )


def _build_match(
    match: Match,
    expected_tournament_id: int | None,
    status: str,
    reason: str,
    candidates: tuple[OddsPapiFixtureDiagnosticCandidate, ...],
    best_fixture_id: str | None,
    best_confidence: Decimal | None,
) -> OddsPapiFixtureDiagnosticMatch:
    return OddsPapiFixtureDiagnosticMatch(
        match_id=match.id,
        league_name=match.league.name,
        source_league_id=str(match.league.source_league_id)
        if match.league.source_league_id is not None
        else None,
        expected_tournament_id=expected_tournament_id,
        kickoff_time_beijing=_format_beijing(match.kickoff_time),
        kickoff_time_utc=_format_utc(match.kickoff_time),
        home_team_name=match.home_team.canonical_name,
        away_team_name=match.away_team.canonical_name,
        status=status,
        reason=reason,
        candidate_count=len(candidates),
        best_fixture_id=best_fixture_id,
        best_confidence=best_confidence,
        candidates=candidates,
    )


def _write_manual_review_csv(report: OddsPapiFixtureDiagnosticReport) -> None:
    with (report.report_dir / "manual_review.csv").open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "match_id",
                "league_name",
                "kickoff_time_beijing",
                "home_team_name",
                "away_team_name",
                "status",
                "reason",
                "best_fixture_id",
                "best_confidence",
                "candidate_count",
            ],
        )
        writer.writeheader()
        for match in report.matches:
            if match.status == "matched":
                continue
            writer.writerow(
                {
                    "match_id": match.match_id,
                    "league_name": match.league_name,
                    "kickoff_time_beijing": match.kickoff_time_beijing,
                    "home_team_name": match.home_team_name,
                    "away_team_name": match.away_team_name,
                    "status": match.status,
                    "reason": match.reason,
                    "best_fixture_id": match.best_fixture_id or "",
                    "best_confidence": str(match.best_confidence)
                    if match.best_confidence is not None
                    else "",
                    "candidate_count": match.candidate_count,
                }
            )


def _format_summary_markdown(report: OddsPapiFixtureDiagnosticReport) -> str:
    lines = [
        "# OddsPapi Fixture Diagnostic",
        "",
        f"- run_id: `{report.run_id}`",
        f"- season: `{report.season}`",
        f"- diagnosed: `{report.diagnosed_match_count}`",
        f"- matched: `{report.matched_count}`",
        f"- manual_review: `{report.manual_review_count}`",
        f"- no_candidate: `{report.no_candidate_count}`",
        f"- missing_mapping: `{report.missing_mapping_count}`",
        f"- api_error: `{report.api_error_count}`",
        f"- skipped_existing_odds: `{report.skipped_existing_odds_count}`",
        f"- requests_used: `{report.requests_used}`",
        "",
        "## Review Targets",
        "",
    ]
    review_matches = [match for match in report.matches if match.status != "matched"]
    if not review_matches:
        lines.append("No manual review targets.")
        return "\n".join(lines) + "\n"
    for match in review_matches[:50]:
        lines.append(
            f"- match_id={match.match_id} {match.league_name} "
            f"{match.kickoff_time_beijing} {match.home_team_name} vs {match.away_team_name} "
            f"status={match.status} reason={match.reason}"
        )
    return "\n".join(lines) + "\n"


def _count_status(matches: tuple[OddsPapiFixtureDiagnosticMatch, ...], status: str) -> int:
    return len([match for match in matches if match.status == status])


def _as_utc(value: datetime, default_timezone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=default_timezone)
    return value.astimezone(UTC_TIMEZONE)


def _format_utc(value: datetime) -> str:
    return _as_utc(value, BEIJING_TIMEZONE).strftime("%Y-%m-%dT%H:%M:%SZ")


def _format_beijing(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=BEIJING_TIMEZONE)
    return value.astimezone(BEIJING_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S")

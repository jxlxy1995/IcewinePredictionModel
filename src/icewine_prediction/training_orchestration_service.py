from __future__ import annotations

import csv
from decimal import Decimal
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from icewine_prediction.baseline_away_cover_stability_service import (
    build_baseline_away_cover_stability_report,
    write_baseline_away_cover_stability_report,
)
from icewine_prediction.baseline_dynamic_feature_set_service import (
    build_baseline_dynamic_feature_set,
    write_baseline_dynamic_feature_set_csv,
    write_baseline_dynamic_feature_set_report,
)
from icewine_prediction.baseline_feature_set_service import (
    build_baseline_feature_set,
    write_baseline_feature_set_csv,
    write_baseline_feature_set_report,
)
from icewine_prediction.baseline_training_dataset_market_baseline_service import (
    build_baseline_training_dataset_market_baseline_report,
    write_baseline_training_dataset_market_baseline_report,
)
from icewine_prediction.baseline_training_dataset_qa_service import (
    build_baseline_training_dataset_qa_report,
    write_baseline_training_dataset_qa_report,
)
from icewine_prediction.baseline_training_dataset_service import (
    build_baseline_training_dataset,
    write_baseline_training_dataset_csv,
    write_baseline_training_dataset_report,
)
from icewine_prediction.models import TrainingRun
from icewine_prediction.time_utils import now_beijing


@dataclass(frozen=True)
class TrainingSnapshotPaths:
    dataset_path: Path
    dataset_report_path: Path
    qa_report_path: Path
    market_baseline_report_path: Path
    feature_path: Path
    feature_report_path: Path
    dynamic_feature_path: Path
    dynamic_feature_report_path: Path
    away_cover_stability_report_path: Path


@dataclass(frozen=True)
class LastTrainedMatchSummary:
    match_id: int
    kickoff_time: datetime
    text: str


@dataclass(frozen=True)
class TrainingOrchestrationSteps:
    write_dataset: Callable[..., dict[str, Any] | None]
    write_qa: Callable[..., None]
    write_market_baseline: Callable[..., None]
    write_feature_set: Callable[..., None]
    write_dynamic_feature_set: Callable[..., None]
    write_away_cover_stability: Callable[..., None]


class TrainingRunAlreadyRunning(Exception):
    def __init__(self, active_run_id: int):
        super().__init__(f"training run {active_run_id} is already running")
        self.active_run_id = active_run_id


def create_training_run(
    session: Session,
    *,
    clock: Callable[[], datetime] = now_beijing,
) -> TrainingRun:
    active_run = (
        session.query(TrainingRun)
        .filter(TrainingRun.run_type == "full_refresh", TrainingRun.status == "running")
        .order_by(TrainingRun.started_at.desc(), TrainingRun.id.desc())
        .first()
    )
    if active_run is not None:
        raise TrainingRunAlreadyRunning(active_run.id)

    started_at = clock()
    run = TrainingRun(
        run_type="full_refresh",
        status="running",
        started_at=started_at,
        snapshot_tag=started_at.strftime("%Y%m%d-%H%M"),
        current_step="queued",
    )
    session.add(run)
    session.flush()
    return run


def get_latest_training_run(session: Session) -> TrainingRun | None:
    return (
        session.query(TrainingRun)
        .filter(TrainingRun.run_type == "full_refresh")
        .order_by(TrainingRun.started_at.desc(), TrainingRun.id.desc())
        .first()
    )


def build_training_snapshot_paths(base_dir: Path, snapshot_tag: str) -> TrainingSnapshotPaths:
    return TrainingSnapshotPaths(
        dataset_path=base_dir / f"local_data/training/baseline_main_leagues_{snapshot_tag}.csv",
        dataset_report_path=base_dir
        / f"docs/数据审计/{snapshot_tag}-baseline-training-dataset.md",
        qa_report_path=base_dir / f"docs/数据审计/{snapshot_tag}-baseline-training-dataset-qa.md",
        market_baseline_report_path=base_dir
        / f"docs/模型实验/{snapshot_tag}-close-market-baseline-evaluation.md",
        feature_path=base_dir / f"local_data/training/baseline_features_main_leagues_{snapshot_tag}.csv",
        feature_report_path=base_dir / f"docs/数据审计/{snapshot_tag}-baseline-feature-set-v1.md",
        dynamic_feature_path=base_dir
        / f"local_data/training/baseline_dynamic_features_main_leagues_{snapshot_tag}.csv",
        dynamic_feature_report_path=base_dir
        / f"docs/数据审计/{snapshot_tag}-baseline-dynamic-feature-set-v1.md",
        away_cover_stability_report_path=base_dir
        / f"docs/模型实验/{snapshot_tag}-baseline-away-cover-stability-v1.md",
    )


def run_training_full_refresh(
    session_factory: Callable[[], Session],
    run_id: int,
    *,
    base_dir: Path = Path("."),
    steps: TrainingOrchestrationSteps | None = None,
    display_league: Callable[[str], str] = lambda value: value,
    display_team: Callable[[str], str] = lambda value: value,
    clock: Callable[[], datetime] = now_beijing,
) -> None:
    steps = steps or build_default_training_orchestration_steps()
    with session_factory() as session:
        run = session.get(TrainingRun, run_id)
        if run is None:
            raise ValueError(f"training run {run_id} not found")
        paths = build_training_snapshot_paths(base_dir, run.snapshot_tag)
        _apply_paths(run, paths)
        session.commit()

    try:
        dataset_metrics = _run_step(
            session_factory,
            run_id,
            "baseline_dataset",
            steps.write_dataset,
            paths,
            with_session=True,
        )
        _record_dataset_metrics(session_factory, run_id, paths, dataset_metrics)
        _run_step(session_factory, run_id, "dataset_qa", steps.write_qa, paths)
        _run_step(session_factory, run_id, "market_baseline", steps.write_market_baseline, paths)
        _run_step(session_factory, run_id, "feature_set", steps.write_feature_set, paths)
        _run_step(
            session_factory,
            run_id,
            "dynamic_feature_set",
            steps.write_dynamic_feature_set,
            paths,
            with_session=True,
        )
        _run_step(
            session_factory,
            run_id,
            "away_cover_stability",
            steps.write_away_cover_stability,
            paths,
        )
    except Exception as error:  # noqa: BLE001 - persisted for Web inspection.
        _mark_failed(session_factory, run_id, str(error), clock=clock)
        return

    summary = extract_last_trained_match_summary(
        paths.dataset_path,
        display_league=display_league,
        display_team=display_team,
    )
    with session_factory() as session:
        run = session.get(TrainingRun, run_id)
        if run is None:
            raise ValueError(f"training run {run_id} not found")
        run.status = "success"
        run.current_step = "finalize"
        run.finished_at = clock()
        run.dataset_rows = _count_csv_rows(paths.dataset_path)
        if summary is not None:
            run.last_trained_match_id = summary.match_id
            run.last_trained_kickoff_time = summary.kickoff_time
            run.last_trained_match_summary = summary.text
        session.commit()


def build_default_training_orchestration_steps() -> TrainingOrchestrationSteps:
    return TrainingOrchestrationSteps(
        write_dataset=_write_dataset,
        write_qa=_write_qa,
        write_market_baseline=_write_market_baseline,
        write_feature_set=_write_feature_set,
        write_dynamic_feature_set=_write_dynamic_feature_set,
        write_away_cover_stability=_write_away_cover_stability,
    )


def extract_last_trained_match_summary(
    csv_path: Path,
    *,
    display_league: Callable[[str], str] = lambda value: value,
    display_team: Callable[[str], str] = lambda value: value,
) -> LastTrainedMatchSummary | None:
    with csv_path.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        return None

    last_row = max(
        rows,
        key=lambda row: (_parse_datetime(row["kickoff_time"]), int(row["match_id"])),
    )
    kickoff_time = _parse_datetime(last_row["kickoff_time"])
    league_name = display_league(last_row.get("league_name", ""))
    home_team = display_team(last_row.get("home_team_name", ""))
    away_team = display_team(last_row.get("away_team_name", ""))
    score = _format_score(last_row)
    text = f"{league_name} {home_team}{score} {away_team}"
    return LastTrainedMatchSummary(
        match_id=int(last_row["match_id"]),
        kickoff_time=kickoff_time,
        text=text,
    )


def _run_step(
    session_factory: Callable[[], Session],
    run_id: int,
    step_name: str,
    step: Callable[..., Any],
    paths: TrainingSnapshotPaths,
    *,
    with_session: bool = False,
) -> Any:
    with session_factory() as session:
        run = session.get(TrainingRun, run_id)
        if run is None:
            raise ValueError(f"training run {run_id} not found")
        run.current_step = step_name
        session.commit()
        if with_session:
            return step(session, paths)
    return step(paths)


def _record_dataset_metrics(
    session_factory: Callable[[], Session],
    run_id: int,
    paths: TrainingSnapshotPaths,
    dataset_metrics: dict[str, Any] | None,
) -> None:
    metrics = dataset_metrics or {}
    with session_factory() as session:
        run = session.get(TrainingRun, run_id)
        if run is None:
            raise ValueError(f"training run {run_id} not found")
        run.dataset_rows = _count_csv_rows(paths.dataset_path)
        if "eligible_matches" in metrics:
            run.eligible_matches = int(metrics["eligible_matches"])
        if "complete_matches" in metrics:
            run.complete_matches = int(metrics["complete_matches"])
        if "coverage_ratio" in metrics:
            run.coverage_ratio = Decimal(str(metrics["coverage_ratio"]))
        session.commit()


def _mark_failed(
    session_factory: Callable[[], Session],
    run_id: int,
    error_message: str,
    *,
    clock: Callable[[], datetime],
) -> None:
    with session_factory() as session:
        run = session.get(TrainingRun, run_id)
        if run is None:
            raise ValueError(f"training run {run_id} not found")
        run.status = "failed"
        run.error_step = run.current_step
        run.error_message = error_message
        run.finished_at = clock()
        session.commit()


def _apply_paths(run: TrainingRun, paths: TrainingSnapshotPaths) -> None:
    run.dataset_path = str(paths.dataset_path)
    run.dataset_report_path = str(paths.dataset_report_path)
    run.qa_report_path = str(paths.qa_report_path)
    run.market_baseline_report_path = str(paths.market_baseline_report_path)
    run.feature_path = str(paths.feature_path)
    run.feature_report_path = str(paths.feature_report_path)
    run.dynamic_feature_path = str(paths.dynamic_feature_path)
    run.dynamic_feature_report_path = str(paths.dynamic_feature_report_path)
    run.away_cover_stability_report_path = str(paths.away_cover_stability_report_path)


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8", newline="") as file:
        return sum(1 for _ in csv.DictReader(file))


def _write_dataset(session: Session, paths: TrainingSnapshotPaths) -> dict[str, Any]:
    dataset = build_baseline_training_dataset(session)
    write_baseline_training_dataset_csv(dataset, paths.dataset_path)
    write_baseline_training_dataset_report(dataset.audit, paths.dataset_report_path)
    return {
        "eligible_matches": dataset.audit.eligible_match_count,
        "complete_matches": dataset.audit.complete_match_count,
        "coverage_ratio": dataset.audit.coverage_ratio,
    }


def _write_qa(paths: TrainingSnapshotPaths) -> None:
    report = build_baseline_training_dataset_qa_report(paths.dataset_path)
    write_baseline_training_dataset_qa_report(report, paths.qa_report_path)


def _write_market_baseline(paths: TrainingSnapshotPaths) -> None:
    report = build_baseline_training_dataset_market_baseline_report(paths.dataset_path)
    write_baseline_training_dataset_market_baseline_report(
        report,
        paths.market_baseline_report_path,
    )


def _write_feature_set(paths: TrainingSnapshotPaths) -> None:
    feature_set = build_baseline_feature_set(paths.dataset_path)
    write_baseline_feature_set_csv(feature_set, paths.feature_path)
    write_baseline_feature_set_report(feature_set.report, paths.feature_report_path)


def _write_dynamic_feature_set(session: Session, paths: TrainingSnapshotPaths) -> None:
    feature_set = build_baseline_dynamic_feature_set(session, paths.feature_path)
    write_baseline_dynamic_feature_set_csv(feature_set, paths.dynamic_feature_path)
    write_baseline_dynamic_feature_set_report(
        feature_set.report,
        paths.dynamic_feature_report_path,
    )


def _write_away_cover_stability(paths: TrainingSnapshotPaths) -> None:
    report = build_baseline_away_cover_stability_report(paths.dynamic_feature_path)
    write_baseline_away_cover_stability_report(report, paths.away_cover_stability_report_path)


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _format_score(row: dict[str, str]) -> str:
    home_score = row.get("home_score") or row.get("target_home_score")
    away_score = row.get("away_score") or row.get("target_away_score")
    if home_score not in (None, "") and away_score not in (None, ""):
        return f" {home_score}-{away_score}"
    return " vs"

from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from icewine_prediction.database import (
    create_memory_database,
    create_session_factory,
    initialize_database,
)
from icewine_prediction.models import TrainingRun
from icewine_prediction.training_orchestration_service import (
    build_default_training_experiments,
    build_training_snapshot_paths,
    extract_last_trained_match_summary,
    TrainingRunAlreadyRunning,
    TrainingExperiment,
    TrainingOrchestrationSteps,
    create_training_run,
    get_latest_training_run,
    run_training_full_refresh,
)


def test_training_run_persists_lifecycle_metadata():
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        run = TrainingRun(
            run_type="full_refresh",
            status="running",
            started_at=datetime(2026, 5, 30, 13, 23, tzinfo=ZoneInfo("Asia/Shanghai")),
            snapshot_tag="20260530-1323",
            current_step="baseline_dataset",
        )
        session.add(run)
        session.commit()
        run_id = run.id

    with session_factory() as session:
        saved = session.get(TrainingRun, run_id)
        assert saved is not None
        assert saved.run_type == "full_refresh"
        assert saved.status == "running"
        assert saved.snapshot_tag == "20260530-1323"
        assert saved.current_step == "baseline_dataset"


def test_create_training_run_uses_beijing_snapshot_tag():
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    clock = lambda: datetime(2026, 5, 30, 13, 23, 45, tzinfo=ZoneInfo("Asia/Shanghai"))

    with session_factory() as session:
        run = create_training_run(session, clock=clock)
        session.commit()

    assert run.status == "running"
    assert run.run_type == "full_refresh"
    assert run.snapshot_tag == "20260530-1323"
    assert run.current_step == "queued"


def test_create_training_run_rejects_existing_running_run():
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    clock = lambda: datetime(2026, 5, 30, 13, 23, tzinfo=ZoneInfo("Asia/Shanghai"))

    with session_factory() as session:
        first = create_training_run(session, clock=clock)
        session.commit()
        try:
            create_training_run(session, clock=clock)
        except TrainingRunAlreadyRunning as error:
            assert error.active_run_id == first.id
        else:
            raise AssertionError("expected TrainingRunAlreadyRunning")


def test_get_latest_training_run_returns_newest_started_run():
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        session.add_all(
            [
                TrainingRun(
                    run_type="full_refresh",
                    status="success",
                    started_at=datetime(2026, 5, 30, 9, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                    snapshot_tag="20260530-0900",
                ),
                TrainingRun(
                    run_type="full_refresh",
                    status="failed",
                    started_at=datetime(2026, 5, 30, 13, 0, tzinfo=ZoneInfo("Asia/Shanghai")),
                    snapshot_tag="20260530-1300",
                ),
            ]
        )
        session.commit()
        latest = get_latest_training_run(session)

    assert latest is not None
    assert latest.snapshot_tag == "20260530-1300"


def test_build_training_snapshot_paths_uses_snapshot_tag(tmp_path):
    paths = build_training_snapshot_paths(tmp_path, "20260530-1323")

    assert paths.dataset_path == (
        tmp_path / "local_data/training/baseline_main_leagues_20260530-1323.csv"
    )
    assert paths.feature_path == (
        tmp_path / "local_data/training/baseline_features_main_leagues_20260530-1323.csv"
    )
    assert paths.dynamic_feature_path == (
        tmp_path
        / "local_data/training/baseline_dynamic_features_main_leagues_20260530-1323.csv"
    )
    assert paths.away_cover_stability_report_path == (
        tmp_path / "docs/模型实验/20260530-1323-baseline-away-cover-stability-v1.md"
    )
    assert paths.experiment_report_paths["away_cover_bucket_threshold_v2"].name == (
        "20260530-1323-baseline-away-cover-bucket-threshold-v2.md"
    )
    assert paths.experiment_report_paths["away_cover_bucket_sandbox_v2"].name == (
        "20260530-1323-baseline-away-cover-bucket-sandbox-v2.md"
    )
    assert paths.experiment_report_paths["total_goals_edge_stability_v1"].name == (
        "20260530-1323-baseline-total-goals-edge-stability-v1.md"
    )
    assert paths.experiment_report_paths["total_goals_bucket_sandbox_v2"].name == (
        "20260530-1323-baseline-total-goals-bucket-sandbox-v2.md"
    )
    assert paths.experiment_report_paths["total_goals_v3_signal_research"].name == (
        "20260530-1323-baseline-total-goals-v3-signal-research.md"
    )
    assert paths.experiment_report_paths["model_consensus_signal_research"].name == (
        "20260530-1323-baseline-model-consensus-signal-research.md"
    )


def test_default_training_experiments_include_signal_research_reports():
    keys = {experiment.key for experiment in build_default_training_experiments()}

    assert "total_goals_v3_signal_research" in keys
    assert "model_consensus_signal_research" in keys


def test_extract_last_trained_match_summary_uses_latest_kickoff_and_display_names(tmp_path):
    csv_path = tmp_path / "baseline.csv"
    csv_path.write_text(
        "match_id,kickoff_time,league_name,home_team_name,away_team_name,home_score,away_score\n"
        "1,2026-05-29T20:00:00+08:00,J1 League,Kobe,Tokyo,1,1\n"
        "2,2026-05-30T18:00:00+08:00,J1 League,Kashima,Nagoya,2,0\n",
        encoding="utf-8",
    )

    summary = extract_last_trained_match_summary(
        csv_path,
        display_league=lambda value: "日职联" if value == "J1 League" else value,
        display_team=lambda value: {"Kashima": "鹿岛鹿角", "Nagoya": "名古屋鲸八"}.get(
            value, value
        ),
    )

    assert summary.match_id == 2
    assert summary.kickoff_time.isoformat() == "2026-05-30T18:00:00+08:00"
    assert summary.text == "日职联 鹿岛鹿角 2-0 名古屋鲸八"


def test_run_training_full_refresh_records_step_order_and_success(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    calls: list[str] = []

    def write_dataset(session, paths):
        calls.append("baseline_dataset")
        paths.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        paths.dataset_path.write_text(
            "match_id,kickoff_time,league_name,home_team_name,away_team_name,home_score,away_score\n"
            "7,2026-05-30T18:00:00+08:00,J1 League,Kobe,Kashima,1,0\n",
            encoding="utf-8",
        )
        return {"eligible_matches": 10, "complete_matches": 1, "coverage_ratio": "0.1000"}

    def touch(name):
        def step(*args):
            calls.append(name)

        return step

    def touch_experiment(name):
        def step(paths, output_path):
            calls.append(name)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("experiment report\n", encoding="utf-8")

        return step

    with session_factory() as session:
        run = create_training_run(
            session,
            clock=lambda: datetime(2026, 5, 30, 13, 23, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        session.commit()
        run_id = run.id

    steps = TrainingOrchestrationSteps(
        write_dataset=write_dataset,
        write_qa=touch("dataset_qa"),
        write_market_baseline=touch("market_baseline"),
        write_feature_set=touch("feature_set"),
        write_dynamic_feature_set=touch("dynamic_feature_set"),
        experiments=(
            TrainingExperiment(
                key="away_cover_stability",
                report_filename="baseline-away-cover-stability-v1.md",
                runner=touch_experiment("away_cover_stability"),
            ),
        ),
    )

    run_training_full_refresh(
        session_factory,
        run_id,
        base_dir=tmp_path,
        steps=steps,
        display_league=lambda value: "日职联" if value == "J1 League" else value,
        display_team=lambda value: {"Kobe": "神户胜利船", "Kashima": "鹿岛鹿角"}.get(
            value, value
        ),
        clock=lambda: datetime(2026, 5, 30, 13, 24, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    with session_factory() as session:
        saved = session.get(TrainingRun, run_id)

    assert calls == [
        "baseline_dataset",
        "dataset_qa",
        "market_baseline",
        "feature_set",
        "dynamic_feature_set",
        "away_cover_stability",
    ]
    assert saved.status == "success"
    assert saved.finished_at == datetime(2026, 5, 30, 13, 24)
    assert saved.dataset_rows == 1
    assert saved.eligible_matches == 10
    assert saved.complete_matches == 1
    assert saved.coverage_ratio == Decimal("0.1000")
    assert saved.last_trained_match_id == 7
    assert saved.last_trained_match_summary == "日职联 神户胜利船 1-0 鹿岛鹿角"


def test_run_training_full_refresh_runs_registered_experiments(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)
    calls: list[str] = []

    def write_dataset(session, paths):
        calls.append("baseline_dataset")
        paths.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        paths.dataset_path.write_text(
            "match_id,kickoff_time,league_name,home_team_name,away_team_name,home_score,away_score\n"
            "7,2026-05-30T18:00:00+08:00,J1 League,Kobe,Kashima,1,0\n",
            encoding="utf-8",
        )
        return {"eligible_matches": 10, "complete_matches": 1, "coverage_ratio": "0.1000"}

    def noop(*args):
        return None

    def write_experiment(paths, output_path):
        calls.append(output_path.name)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text("experiment report\n", encoding="utf-8")

    with session_factory() as session:
        run = create_training_run(
            session,
            clock=lambda: datetime(2026, 5, 30, 13, 23, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        session.commit()
        run_id = run.id

    steps = TrainingOrchestrationSteps(
        write_dataset=write_dataset,
        write_qa=noop,
        write_market_baseline=noop,
        write_feature_set=noop,
        write_dynamic_feature_set=noop,
        experiments=(
            TrainingExperiment(
                key="custom_experiment",
                report_filename="custom-experiment.md",
                runner=write_experiment,
            ),
        ),
    )

    run_training_full_refresh(
        session_factory,
        run_id,
        base_dir=tmp_path,
        steps=steps,
        display_league=lambda value: value,
        display_team=lambda value: value,
        clock=lambda: datetime(2026, 5, 30, 13, 24, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    with session_factory() as session:
        saved = session.get(TrainingRun, run_id)

    assert "custom-experiment.md" in calls
    assert saved.status == "success"
    assert any(path.name == "custom-experiment.md" for path in tmp_path.rglob("*.md"))


def test_run_training_full_refresh_records_failed_step(tmp_path):
    engine = create_memory_database()
    initialize_database(engine)
    session_factory = create_session_factory(engine)

    def write_dataset(session, paths):
        paths.dataset_path.parent.mkdir(parents=True, exist_ok=True)
        paths.dataset_path.write_text(
            "match_id,kickoff_time,league_name,home_team_name,away_team_name,home_score,away_score\n"
            "8,2026-05-30T18:00:00+08:00,J1 League,Kobe,Kashima,1,0\n",
            encoding="utf-8",
        )
        return {"eligible_matches": 12, "complete_matches": 1, "coverage_ratio": "0.0833"}

    def fail_feature_set(*args):
        raise RuntimeError("feature builder exploded")

    def noop(*args):
        return None

    with session_factory() as session:
        run = create_training_run(
            session,
            clock=lambda: datetime(2026, 5, 30, 13, 23, tzinfo=ZoneInfo("Asia/Shanghai")),
        )
        session.commit()
        run_id = run.id

    steps = TrainingOrchestrationSteps(
        write_dataset=write_dataset,
        write_qa=noop,
        write_market_baseline=noop,
        write_feature_set=fail_feature_set,
        write_dynamic_feature_set=noop,
        experiments=(),
    )

    run_training_full_refresh(
        session_factory,
        run_id,
        base_dir=tmp_path,
        steps=steps,
        display_league=lambda value: value,
        display_team=lambda value: value,
        clock=lambda: datetime(2026, 5, 30, 13, 25, tzinfo=ZoneInfo("Asia/Shanghai")),
    )

    with session_factory() as session:
        saved = session.get(TrainingRun, run_id)

    assert saved.status == "failed"
    assert saved.error_step == "feature_set"
    assert saved.error_message == "feature builder exploded"
    assert saved.dataset_path.endswith("baseline_main_leagues_20260530-1323.csv")
    assert saved.complete_matches == 1

from pathlib import Path
import json

from icewine_prediction.oddspapi_worker_process_service import (
    build_oddspapi_batch_worker_status,
    start_oddspapi_batch_worker_process,
)


def test_start_batch_worker_process_writes_status_and_launches_python(monkeypatch, tmp_path):
    captured = {}

    class FakeProcess:
        pid = 4321

    def fake_popen(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return FakeProcess()

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    result = start_oddspapi_batch_worker_process(
        season=2025,
        mode="balanced",
        chunk_size=10,
        request_budget_per_league=500,
        timeout_seconds=20,
        max_snapshots_per_match=120,
        max_rounds_per_league=2,
        stop_after_empty_matches=8,
        stop_after_failed_rounds=2,
        round_timeout_seconds=60,
        historical_odds_cooldown_seconds=7.5,
        hard_timeout_seconds=3600,
        log_dir=tmp_path,
        league_ids={"41", "89"},
        from_date="2026-01-15",
        skip_match_ids={8328, 8600},
        match_ids={9001, 9002},
        notify_on_complete=True,
    )

    command = captured["command"]
    assert command[1:4] == ["-m", "icewine_cli", "odds-source"]
    assert "oddspapi-batch-worker" in command
    assert command[command.index("--league-ids") + 1] == "41,89"
    assert command[command.index("--from-date") + 1] == "2026-01-15"
    assert command[command.index("--skip-match-ids") + 1] == "8328,8600"
    assert command[command.index("--match-ids") + 1] == "9001,9002"
    assert command[command.index("--stop-after-failed-rounds") + 1] == "2"
    assert command[command.index("--round-timeout-seconds") + 1] == "60"
    assert command[command.index("--historical-odds-cooldown-seconds") + 1] == "7.5"
    assert command[command.index("--hard-timeout-seconds") + 1] == "3600"
    assert "--notify-on-complete" in command
    assert captured["kwargs"]["cwd"] == Path.cwd()
    assert captured["kwargs"]["env"]["PYTHONIOENCODING"] == "utf-8"
    assert captured["kwargs"]["env"]["PYTHONPATH"].split(";")[0] == "src"
    assert result.pid == 4321
    assert result.status_path.exists()
    assert "已启动 OddsPapi 后台回填 pid=4321" in result.to_text()


def test_batch_worker_status_reads_current_status_and_log_tail(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "icewine_prediction.oddspapi_worker_process_service._is_process_running",
        lambda pid: True,
    )
    start_result = start_oddspapi_batch_worker_process(
        season=2025,
        mode="safe",
        chunk_size=1,
        request_budget_per_league=5,
        timeout_seconds=20,
        max_snapshots_per_match=120,
        max_rounds_per_league=1,
        stop_after_empty_matches=8,
        stop_after_failed_rounds=2,
        round_timeout_seconds=60,
        historical_odds_cooldown_seconds=7.5,
        hard_timeout_seconds=3600,
        log_dir=tmp_path,
        league_ids={"62"},
        from_date=None,
        skip_match_ids=None,
        match_ids=None,
        notify_on_complete=False,
        popen_factory=lambda command, **kwargs: type("FakeProcess", (), {"pid": 9876})(),
    )
    start_result.log_path.write_text("line one\nline two\nline three\n", encoding="utf-8")

    output = build_oddspapi_batch_worker_status(log_dir=tmp_path, tail_lines=2)

    assert "pid=9876 status=running" in output
    assert str(start_result.log_path) in output
    assert "line two" in output
    assert "line three" in output
    assert "line one" not in output


def test_batch_worker_status_includes_progress_snapshot(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "icewine_prediction.oddspapi_worker_process_service._is_process_running",
        lambda pid: True,
    )
    start_result = start_oddspapi_batch_worker_process(
        season=2025,
        mode="safe",
        chunk_size=1,
        request_budget_per_league=5,
        timeout_seconds=20,
        max_snapshots_per_match=120,
        max_rounds_per_league=1,
        stop_after_empty_matches=8,
        stop_after_failed_rounds=2,
        round_timeout_seconds=60,
        historical_odds_cooldown_seconds=7.5,
        hard_timeout_seconds=3600,
        log_dir=tmp_path,
        league_ids={"62"},
        from_date=None,
        skip_match_ids=None,
        match_ids=None,
        notify_on_complete=False,
        popen_factory=lambda command, **kwargs: type("FakeProcess", (), {"pid": 9876})(),
    )
    start_result.log_path.write_text("鍚姩鏃ュ織\n", encoding="utf-8")
    (tmp_path / "oddspapi-worker-progress.json").write_text(
        json.dumps(
            {
                "status": "running",
                "mode": "safe",
                "season": 2025,
                "worker_count": 1,
                "league_count": 1,
                "total_matches": 20,
                "progress_percent": 40.0,
                "updated_at": "2026-05-26T21:50:00+08:00",
                "current_league": {
                    "league_id": "62",
                    "league_name": "Ligue 2",
                    "total_matches": 20,
                    "progress_percent": 40.0,
                    "round": 3,
                    "processed_matches": 8,
                    "failed_matches": 1,
                    "inserted_snapshots": 720,
                    "requests_used": 24,
                    "last_round": {
                        "processed_matches": 1,
                        "inserted_snapshots": 100,
                        "failed_matches": 0,
                        "requests_used": 5,
                    },
                },
                "totals": {
                    "processed_matches": 8,
                    "failed_matches": 1,
                    "inserted_snapshots": 720,
                    "requests_used": 24,
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output = build_oddspapi_batch_worker_status(log_dir=tmp_path, tail_lines=1)

    assert "进度快照" in output
    assert "状态 running updated_at=2026-05-26T21:50:00+08:00" in output
    assert "当前 Ligue 2 id=62 progress=8/20 (40.0%) round=3 processed=8 snapshots=720 failed=1 requests=24" in output
    assert "上一轮 processed=1 snapshots=100 failed=0 requests=5" in output
    assert "总计 progress=8/20 (40.0%) processed=8 snapshots=720 failed=1 requests=24" in output


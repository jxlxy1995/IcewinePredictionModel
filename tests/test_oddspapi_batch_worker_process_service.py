from pathlib import Path

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
        log_dir=tmp_path,
        league_ids={"41", "89"},
        from_date="2026-01-15",
        notify_on_complete=True,
    )

    command = captured["command"]
    assert command[1:4] == ["-m", "icewine_cli", "odds-source"]
    assert "oddspapi-batch-worker" in command
    assert command[command.index("--league-ids") + 1] == "41,89"
    assert command[command.index("--from-date") + 1] == "2026-01-15"
    assert command[command.index("--stop-after-failed-rounds") + 1] == "2"
    assert command[command.index("--round-timeout-seconds") + 1] == "60"
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
        log_dir=tmp_path,
        league_ids={"62"},
        from_date=None,
        notify_on_complete=False,
        popen_factory=lambda command, **kwargs: type("FakeProcess", (), {"pid": 9876})(),
    )
    start_result.log_path.write_text("第一行\n第二行\n第三行\n", encoding="utf-8")

    output = build_oddspapi_batch_worker_status(log_dir=tmp_path, tail_lines=2)

    assert "pid=9876 status=running" in output
    assert str(start_result.log_path) in output
    assert "第二行" in output
    assert "第三行" in output
    assert "第一行" not in output

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Callable, Sequence

from icewine_prediction.time_utils import now_beijing


@dataclass(frozen=True)
class WorkerStartResult:
    pid: int
    status_path: Path
    log_path: Path
    command: tuple[str, ...]

    def to_text(self) -> str:
        return "\n".join(
            [
                f"已启动 OddsPapi 后台回填 pid={self.pid}",
                f"状态文件 {self.status_path}",
                f"日志文件 {self.log_path}",
                f"命令 {' '.join(self.command)}",
            ]
        )


def start_oddspapi_batch_worker_process(
    *,
    season: int,
    mode: str,
    chunk_size: int,
    request_budget_per_league: int,
    timeout_seconds: int,
    max_snapshots_per_match: int,
    max_rounds_per_league: int,
    stop_after_empty_matches: int,
    stop_after_failed_rounds: int,
    round_timeout_seconds: float,
    historical_odds_cooldown_seconds: float,
    hard_timeout_seconds: float,
    log_dir: str | Path,
    league_ids: set[str] | None,
    from_date: str | None,
    skip_match_ids: set[int] | None,
    notify_on_complete: bool = False,
    popen_factory: Callable[..., subprocess.Popen] | None = None,
) -> WorkerStartResult:
    log_dir = Path(log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    started_at = now_beijing().strftime("%Y%m%d-%H%M%S")
    output_log_path = log_dir / f"{started_at}-oddspapi-worker-process.log"
    status_path = log_dir / "oddspapi-worker-current.json"
    command = _build_worker_command(
        season=season,
        mode=mode,
        chunk_size=chunk_size,
        request_budget_per_league=request_budget_per_league,
        timeout_seconds=timeout_seconds,
        max_snapshots_per_match=max_snapshots_per_match,
        max_rounds_per_league=max_rounds_per_league,
        stop_after_empty_matches=stop_after_empty_matches,
        stop_after_failed_rounds=stop_after_failed_rounds,
        round_timeout_seconds=round_timeout_seconds,
        historical_odds_cooldown_seconds=historical_odds_cooldown_seconds,
        hard_timeout_seconds=hard_timeout_seconds,
        log_dir=log_dir,
        league_ids=league_ids,
        from_date=from_date,
        skip_match_ids=skip_match_ids,
        notify_on_complete=notify_on_complete,
    )
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONPATH"] = _prepend_pythonpath("src", env.get("PYTHONPATH", ""))
    popen = popen_factory or subprocess.Popen
    with output_log_path.open("a", encoding="utf-8") as stdout:
        process = popen(
            list(command),
            cwd=Path.cwd(),
            env=env,
            stdout=stdout,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            start_new_session=True,
        )
    status = {
        "pid": process.pid,
        "started_at": now_beijing().isoformat(),
        "status": "started",
        "command": list(command),
        "process_log_path": str(output_log_path),
        "worker_log_dir": str(log_dir),
        "season": season,
        "mode": mode,
        "league_ids": sorted(league_ids or []),
        "from_date": from_date,
        "skip_match_ids": sorted(skip_match_ids or []),
        "notify_on_complete": notify_on_complete,
        "stop_after_failed_rounds": stop_after_failed_rounds,
        "round_timeout_seconds": round_timeout_seconds,
        "historical_odds_cooldown_seconds": historical_odds_cooldown_seconds,
        "hard_timeout_seconds": hard_timeout_seconds,
    }
    status_path.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    return WorkerStartResult(
        pid=process.pid,
        status_path=status_path,
        log_path=output_log_path,
        command=command,
    )


def build_oddspapi_batch_worker_status(
    *,
    log_dir: str | Path,
    tail_lines: int = 30,
) -> str:
    log_dir = Path(log_dir)
    status_path = log_dir / "oddspapi-worker-current.json"
    if not status_path.exists():
        return f"暂无 OddsPapi 后台回填状态：{status_path} 不存在"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    pid = int(status["pid"])
    running_text = "running" if _is_process_running(pid) else "stopped"
    process_log_path = Path(status["process_log_path"])
    lines = [
        f"pid={pid} status={running_text}",
        f"started_at={status.get('started_at')}",
        f"mode={status.get('mode')} season={status.get('season')}",
        f"league_ids={','.join(status.get('league_ids') or []) or '-'}",
        f"log={process_log_path}",
    ]
    tail = _read_log_tail(process_log_path, tail_lines=tail_lines)
    if tail:
        lines.append("最近日志：")
        lines.extend(tail)
    return "\n".join(lines)


def _build_worker_command(
    *,
    season: int,
    mode: str,
    chunk_size: int,
    request_budget_per_league: int,
    timeout_seconds: int,
    max_snapshots_per_match: int,
    max_rounds_per_league: int,
    stop_after_empty_matches: int,
    stop_after_failed_rounds: int,
    round_timeout_seconds: float,
    historical_odds_cooldown_seconds: float,
    hard_timeout_seconds: float,
    log_dir: Path,
    league_ids: set[str] | None,
    from_date: str | None,
    skip_match_ids: set[int] | None,
    notify_on_complete: bool = False,
) -> tuple[str, ...]:
    command = [
        sys.executable,
        "-m",
        "icewine_cli",
        "odds-source",
        "oddspapi-batch-worker",
        "--season",
        str(season),
        "--mode",
        mode,
        "--chunk-size",
        str(chunk_size),
        "--request-budget-per-league",
        str(request_budget_per_league),
        "--timeout-seconds",
        str(timeout_seconds),
        "--max-snapshots-per-match",
        str(max_snapshots_per_match),
        "--max-rounds-per-league",
        str(max_rounds_per_league),
        "--stop-after-empty-matches",
        str(stop_after_empty_matches),
        "--stop-after-failed-rounds",
        str(stop_after_failed_rounds),
        "--round-timeout-seconds",
        str(round_timeout_seconds),
        "--historical-odds-cooldown-seconds",
        str(historical_odds_cooldown_seconds),
        "--hard-timeout-seconds",
        str(hard_timeout_seconds),
        "--log-dir",
        str(log_dir),
    ]
    if league_ids:
        command.extend(["--league-ids", ",".join(sorted(league_ids))])
    if from_date:
        command.extend(["--from-date", from_date])
    if skip_match_ids:
        command.extend(["--skip-match-ids", ",".join(str(value) for value in sorted(skip_match_ids))])
    if notify_on_complete:
        command.append("--notify-on-complete")
    return tuple(command)


def _prepend_pythonpath(path: str, current_value: str) -> str:
    if not current_value:
        return path
    return f"{path}{os.pathsep}{current_value}"


def _is_process_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _is_windows_process_running(pid)
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _is_windows_process_running(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    still_active = 259
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def _read_log_tail(path: Path, *, tail_lines: int) -> list[str]:
    if tail_lines <= 0 or not path.exists():
        return []
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-tail_lines:]

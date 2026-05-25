from __future__ import annotations

import os
import subprocess


def notify_local_completion(title: str, message: str) -> bool:
    if os.name == "nt":
        return _notify_windows(title, message)
    return _beep()


def _notify_windows(title: str, message: str) -> bool:
    popup_ok = _run_without_waiting(
        [
            "powershell",
            "-NoProfile",
            "-WindowStyle",
            "Hidden",
            "-Command",
            (
                "Add-Type -AssemblyName PresentationFramework; "
                f"[System.Windows.MessageBox]::Show({_ps_quote(message)}, {_ps_quote(title)}) | Out-Null"
            ),
        ]
    )
    beep_ok = _beep()
    return popup_ok or beep_ok


def _beep() -> bool:
    if os.name != "nt":
        return False
    return _run_without_waiting(
        [
            "powershell",
            "-NoProfile",
            "-WindowStyle",
            "Hidden",
            "-Command",
            "[console]::beep(880,500)",
        ]
    )


def _run_without_waiting(command: list[str]) -> bool:
    try:
        subprocess.Popen(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except OSError:
        return False
    return True


def _ps_quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"

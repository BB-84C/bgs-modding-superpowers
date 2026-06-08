"""Runtime PID tracking for GUI-alive detection."""

from __future__ import annotations

import ctypes
import os
from pathlib import Path

from bgs_translator.config import paths


def PID_FILE() -> Path:
    """Return the GUI PID marker path."""

    return paths.translator_root() / "gui.pid"


def write_gui_pid() -> None:
    """Write this process' PID for CLI-side GUI discovery."""

    pid_file = PID_FILE()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()), encoding="utf-8")


def remove_gui_pid() -> None:
    """Remove the GUI PID marker on shutdown."""

    try:
        PID_FILE().unlink()
    except FileNotFoundError:
        pass


def is_gui_alive() -> tuple[bool, int | None]:
    """Return whether the PID marker points at a currently running process."""

    pid_file = PID_FILE()
    if not pid_file.exists():
        return False, None
    try:
        pid = int(pid_file.read_text(encoding="utf-8").strip())
    except (ValueError, OSError):
        return False, None
    if pid <= 0:
        return False, None
    if os.name == "nt":
        return _is_windows_process_alive(pid)
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False, None
    return True, pid


def _is_windows_process_alive(pid: int) -> tuple[bool, int | None]:
    process_query_limited_information = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(
        process_query_limited_information,
        False,
        pid,
    )
    if not handle:
        return False, None
    try:
        exit_code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(
            handle,
            ctypes.byref(exit_code),
        )
        still_active = 259
        if ok and exit_code.value == still_active:
            return True, pid
        return False, None
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


__all__ = ["PID_FILE", "is_gui_alive", "remove_gui_pid", "write_gui_pid"]

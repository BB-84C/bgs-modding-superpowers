"""Runtime PID tracking tests."""

from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_write_gui_pid_creates_file_with_current_pid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.core import runtime_pid

    runtime_pid.write_gui_pid()

    pid_path = tmp_path / "translator" / "gui.pid"
    assert pid_path.read_text(encoding="utf-8") == str(os.getpid())


def test_is_gui_alive_returns_true_for_current_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.core import runtime_pid

    runtime_pid.write_gui_pid()

    assert runtime_pid.is_gui_alive() == (True, os.getpid())


def test_is_gui_alive_returns_false_when_pid_file_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.core import runtime_pid

    assert runtime_pid.is_gui_alive() == (False, None)


def test_is_gui_alive_returns_false_for_dead_pid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.core import runtime_pid

    pid_path = tmp_path / "translator" / "gui.pid"
    pid_path.parent.mkdir(parents=True)
    pid_path.write_text("99999999", encoding="utf-8")

    assert runtime_pid.is_gui_alive() == (False, None)


def test_remove_gui_pid_deletes_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BGS_MODDING_SUPERPOWERS_HOME", str(tmp_path))
    from bgs_translator.core import runtime_pid

    runtime_pid.write_gui_pid()
    runtime_pid.remove_gui_pid()

    assert not (tmp_path / "translator" / "gui.pid").exists()

"""Shared safety checks for the live-bridge unit-test suite."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path


import pytest


_ROOT_ANCHOR = Path.cwd().anchor
_ROOT_ENTRIES_BEFORE = {entry.name for entry in Path(_ROOT_ANCHOR).iterdir()}


def _entry_details(name: str) -> str:
    entry = Path(_ROOT_ANCHOR) / name
    try:
        stat = entry.stat()
    except FileNotFoundError:
        return f"{name} (entry disappeared before metadata read)"
    kind = "dir" if entry.is_dir() else "file"
    created = datetime.fromtimestamp(stat.st_ctime).isoformat(timespec="seconds")
    modified = datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds")
    return f"{name} ({kind}, created={created}, modified={modified})"


def pytest_sessionstart(session) -> None:
    # Keep this hook for an explicit session-level record, while the module-level
    # snapshot remains valid when pytest loads this conftest after sessionstart.
    session.config._drive_root_entries_before = _ROOT_ENTRIES_BEFORE


def pytest_sessionfinish(session, exitstatus) -> None:
    added = sorted(
        entry.name
        for entry in Path(_ROOT_ANCHOR).iterdir()
        if entry.name not in _ROOT_ENTRIES_BEFORE
    )
    if not added:
        return

    session.exitstatus = exitstatus or pytest.ExitCode.TESTS_FAILED
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_sep(
            "!",
            "drive-root guard detected new top-level entries under "
            f"{_ROOT_ANCHOR}: {', '.join(_entry_details(name) for name in added)}; "
            "may also be a concurrent process; identify the owner before deleting; never auto-delete.",
        )

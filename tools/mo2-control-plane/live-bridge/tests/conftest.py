"""Shared safety checks for the live-bridge unit-test suite."""

from __future__ import annotations

from pathlib import Path


def _root_entries() -> set[str]:
    root = Path.cwd().anchor
    return {entry.name for entry in Path(root).iterdir()}


def pytest_sessionstart(session) -> None:
    session.config._drive_root_entries_before = _root_entries()


def pytest_sessionfinish(session, exitstatus) -> None:
    before = session.config._drive_root_entries_before
    added = sorted(_root_entries() - before)
    if not added:
        return

    session.exitstatus = 1
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if reporter is not None:
        reporter.write_sep(
            "!",
            f"drive-root guard detected new top-level entries under {Path.cwd().anchor}: {', '.join(added)}",
        )

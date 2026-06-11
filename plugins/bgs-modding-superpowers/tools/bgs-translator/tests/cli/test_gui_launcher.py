"""GUI launcher routing regressions."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from typer.testing import CliRunner


def test_gui_defaults_to_web_backend(monkeypatch) -> None:
    from bgs_translator.cli.gui_launcher import launch_gui

    calls: list[dict[str, Any]] = []
    module = ModuleType("bgs_translator.web.app")

    def fake_launch_web(**kwargs: Any) -> None:
        calls.append(kwargs)

    module.launch_web = fake_launch_web  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "bgs_translator.web.app", module)

    launch_gui(theme="amber", language="zh-cn", no_open=True)

    assert calls == [{"theme": "amber", "language": "zh-cn", "port": None, "no_open": True, "native": False}]


def test_gui_backend_option_is_removed() -> None:
    from bgs_translator.cli.app import app

    result = CliRunner().invoke(app, ["gui", "--backend", "tk"])

    assert result.exit_code != 0
    assert "No such option" in result.output

"""GUI launcher routing regressions."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any


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


def test_gui_keeps_tk_backend_opt_in(monkeypatch) -> None:
    from bgs_translator.cli.gui_launcher import launch_gui

    calls: list[dict[str, Any]] = []
    module = ModuleType("bgs_translator.gui.app")

    def fake_launch(**kwargs: Any) -> None:
        calls.append(kwargs)

    module.launch = fake_launch  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "bgs_translator.gui.app", module)

    launch_gui(theme="amber", language="zh-cn", backend="tk")

    assert calls == [{"theme": "amber", "language": "zh-cn"}]

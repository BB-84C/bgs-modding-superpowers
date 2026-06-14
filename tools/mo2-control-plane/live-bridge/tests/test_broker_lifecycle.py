import ctypes
import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock


LIVE_BRIDGE_DIR = Path(__file__).resolve().parents[1]


class _FakeWinFunction:
    def __call__(self, *args, **kwargs):
        return 1


class _FakeWinDll:
    def __getattr__(self, name):
        function = _FakeWinFunction()
        setattr(self, name, function)
        return function


def _load_bridge(monkeypatch):
    monkeypatch.syspath_prepend(str(LIVE_BRIDGE_DIR))
    monkeypatch.setitem(
        sys.modules,
        "mobase",
        types.SimpleNamespace(IPluginTool=object, VersionInfo=lambda *args: args),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: _FakeWinDll(), raising=False)

    pyqt6_module = types.ModuleType("PyQt6")
    qt_core_module = types.ModuleType("PyQt6.QtCore")

    class FakeQCoreApplication:
        quit = MagicMock()

    class FakeQTimer:
        pass

    qt_core_module.QCoreApplication = FakeQCoreApplication
    qt_core_module.QTimer = FakeQTimer
    pyqt6_module.QtCore = qt_core_module
    monkeypatch.setitem(sys.modules, "PyQt6", pyqt6_module)
    monkeypatch.setitem(sys.modules, "PyQt6.QtCore", qt_core_module)

    sys.modules.pop("mo2_agent_control", None)
    return importlib.import_module("mo2_agent_control")


def test_shutdown_response_returned_and_hook_queued(monkeypatch):
    """P-B2: handler returns ok response synchronously and queues quit as post-response hook."""

    bridge = _load_bridge(monkeypatch)
    bridge._post_response_hooks.clear()

    fake_pump = MagicMock()
    fake_pump.enqueue = MagicMock()
    monkeypatch.setattr(bridge, "_get_main_thread_pump", lambda: fake_pump)

    response = bridge._handle_system_shutdown(organizer=None, payload={})

    assert response["ok"] is True
    assert response["result"]["shutting_down"] is True
    assert response["error"] is None
    assert len(bridge._post_response_hooks) == 1
    fake_pump.enqueue.assert_not_called()

    bridge.drain_post_response_hooks()
    fake_pump.enqueue.assert_called_once()


def test_drain_continues_on_hook_exception(monkeypatch):
    """A misbehaving hook must not stop subsequent hooks from running."""

    bridge = _load_bridge(monkeypatch)
    bridge._post_response_hooks.clear()
    calls = []

    bridge.register_post_response_hook(lambda: (_ for _ in ()).throw(RuntimeError("boom")))
    bridge.register_post_response_hook(lambda: calls.append("second"))

    bridge.drain_post_response_hooks()

    assert calls == ["second"]
    assert bridge._post_response_hooks == []

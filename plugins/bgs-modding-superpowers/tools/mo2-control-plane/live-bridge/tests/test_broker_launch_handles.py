"""launch.start owns organizer HANDLEs; registry entries contain process IDs."""

import ctypes
import importlib
import json
from pathlib import Path
import subprocess
import sys
import types
from unittest.mock import Mock

import pytest


def load_bridge(monkeypatch, *, native=False):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    monkeypatch.setitem(sys.modules, "mobase", types.SimpleNamespace(IPluginTool=object))
    if not native:
        monkeypatch.setattr(ctypes, "WinDLL", lambda *a, **kw: Mock(), raising=False)
    sys.modules.pop("mo2_agent_control", None)
    return importlib.import_module("mo2_agent_control")


def request():
    return {
        "protocol_version": "1", "request_id": "handle-test", "session_id": "handle-test",
        "method": "launch.start",
        "payload": {"transport": {"target_path": "fake.exe", "args": ["arg"], "cwd": "work"}},
    }


def dispatch(bridge, organizer):
    registry = bridge.create_launch_registry()
    handlers = bridge.build_command_handlers(
        registry, organizer=organizer, main_thread_pump=bridge.MainThreadCallPump(),
    )
    return bridge.dispatch_transport_request(request(), handlers), registry


@pytest.mark.parametrize("handle", [123, 0x1234567887654321])
def test_registry_records_pid_not_handle_and_closes_once(monkeypatch, handle):
    bridge = load_bridge(monkeypatch)
    bridge.KERNEL32.GetProcessId.return_value = 4242
    organizer = types.SimpleNamespace(startApplication=Mock(return_value=handle))
    fallback = Mock(side_effect=AssertionError("must stay inside organizer"))
    monkeypatch.setattr(bridge, "start_subprocess_launch", fallback)

    response, registry = dispatch(bridge, organizer)

    assert response["ok"] is True
    assert response["result"]["pid"] == 4242
    assert response["result"]["artifacts"]["backend"] == "organizer"
    entry = registry[bridge.LAUNCH_REGISTRY_ENTRIES_FIELD][response["result"]["launch_id"]]
    assert entry["pid"] == 4242
    organizer.startApplication.assert_called_once_with("fake.exe", ["arg"], "work", "")
    bridge.KERNEL32.GetProcessId.assert_called_once_with(handle)
    bridge.KERNEL32.CloseHandle.assert_called_once_with(handle)
    fallback.assert_not_called()


def test_win32_signatures_preserve_pointer_width(monkeypatch):
    bridge = load_bridge(monkeypatch)
    assert bridge.KERNEL32.GetProcessId.argtypes == [ctypes.c_void_p]
    assert bridge.KERNEL32.GetProcessId.restype is ctypes.c_uint32
    assert bridge.KERNEL32.CloseHandle.argtypes == [ctypes.c_void_p]
    assert bridge.KERNEL32.CloseHandle.restype is ctypes.c_int


@pytest.mark.parametrize("sentinel", [None, 0, -1, ctypes.c_void_p(-1).value, "mobase"])
def test_failure_sentinels_never_publish_success_or_close(monkeypatch, sentinel):
    bridge = load_bridge(monkeypatch)
    if sentinel == "mobase":
        sentinel = 0xBAD
        monkeypatch.setattr(bridge.mobase, "INVALID_HANDLE_VALUE", sentinel, raising=False)
    organizer = types.SimpleNamespace(startApplication=Mock(return_value=sentinel))
    fallback = Mock(side_effect=AssertionError("native failure must not fall back"))
    monkeypatch.setattr(bridge, "start_subprocess_launch", fallback)

    response, registry = dispatch(bridge, organizer)

    assert response["ok"] is False
    assert response.get("result") is None
    assert registry[bridge.LAUNCH_REGISTRY_ENTRIES_FIELD] == {}
    organizer.startApplication.assert_called_once()
    bridge.KERNEL32.GetProcessId.assert_not_called()
    bridge.KERNEL32.CloseHandle.assert_not_called()
    fallback.assert_not_called()


@pytest.mark.parametrize("failure", ["zero", "exception", "type_error"])
def test_conversion_failure_closes_once_without_retry_or_fallback(monkeypatch, failure):
    bridge = load_bridge(monkeypatch)
    handle = 0x1234567887654321
    organizer = types.SimpleNamespace(startApplication=Mock(return_value=handle))
    if failure == "zero":
        bridge.KERNEL32.GetProcessId.return_value = 0
        monkeypatch.setattr(ctypes, "get_last_error", lambda: 5, raising=False)
        monkeypatch.setattr(ctypes, "FormatError", lambda code: "Access denied", raising=False)
    else:
        bridge.KERNEL32.GetProcessId.side_effect = (
            TypeError("conversion failed") if failure == "type_error" else OSError(5, "query failed")
        )
    fallback = Mock(side_effect=AssertionError("native failure must not fall back"))
    monkeypatch.setattr(bridge, "start_subprocess_launch", fallback)

    response, registry = dispatch(bridge, organizer)

    assert response["ok"] is False
    assert registry[bridge.LAUNCH_REGISTRY_ENTRIES_FIELD] == {}
    if failure == "zero":
        assert "5" in response["error"]["message"]
    organizer.startApplication.assert_called_once()
    bridge.KERNEL32.GetProcessId.assert_called_once_with(handle)
    bridge.KERNEL32.CloseHandle.assert_called_once_with(handle)
    fallback.assert_not_called()


@pytest.mark.parametrize("arity", [4, 3, 2])
def test_signature_fallbacks_launch_and_release_only_once(monkeypatch, arity):
    bridge = load_bridge(monkeypatch)
    attempts, acquired = [], []

    def start(*args):
        attempts.append(len(args))
        if len(args) != arity:
            raise TypeError("unsupported signature")
        acquired.append(901)
        return 901

    bridge.KERNEL32.GetProcessId.return_value = 4242
    response, _ = dispatch(bridge, types.SimpleNamespace(startApplication=start))
    assert response["ok"] is True
    assert response["result"]["pid"] == 4242
    assert attempts == list(range(4, arity - 1, -1))
    assert acquired == [901]
    bridge.KERNEL32.GetProcessId.assert_called_once_with(901)
    bridge.KERNEL32.CloseHandle.assert_called_once_with(901)


@pytest.mark.parametrize("error", [TypeError("no supported signature"), RuntimeError("launch failed")])
def test_native_api_failure_does_not_fall_back(monkeypatch, error):
    bridge = load_bridge(monkeypatch)
    organizer = types.SimpleNamespace(startApplication=Mock(side_effect=error))
    fallback = Mock(side_effect=AssertionError("native failure must not fall back"))
    monkeypatch.setattr(bridge, "start_subprocess_launch", fallback)
    response, registry = dispatch(bridge, organizer)
    assert response["ok"] is False
    assert registry[bridge.LAUNCH_REGISTRY_ENTRIES_FIELD] == {}
    fallback.assert_not_called()
    bridge.KERNEL32.CloseHandle.assert_not_called()
    assert organizer.startApplication.call_count == (3 if isinstance(error, TypeError) else 1)


@pytest.mark.parametrize("organizer", [None, object()])
def test_missing_organizer_api_keeps_subprocess_harness_path(monkeypatch, organizer):
    bridge = load_bridge(monkeypatch)
    assert bridge.start_organizer_launch(organizer, {"target_path": "fake.exe"}) is None
    process = types.SimpleNamespace(pid=4242)
    fallback = Mock(return_value=process)
    monkeypatch.setattr(bridge, "start_subprocess_launch", fallback)
    response, _ = dispatch(bridge, organizer)
    assert response["ok"] is True
    assert response["result"]["pid"] == 4242
    assert response["result"]["artifacts"]["backend"] == "subprocess"
    fallback.assert_called_once()
    bridge.KERNEL32.CloseHandle.assert_not_called()


@pytest.mark.skipif(sys.platform != "win32", reason="real Windows HANDLE proof")
def test_real_owned_python_process_handle_conversion_and_release(monkeypatch, tmp_path):
    bridge = load_bridge(monkeypatch, native=True)
    kernel = bridge.KERNEL32
    kernel.GetHandleInformation.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    kernel.GetHandleInformation.restype = ctypes.c_int
    evidence = {"python": sys.executable, "pointer_bits": ctypes.sizeof(ctypes.c_void_p) * 8}
    child = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(1)"],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    try:
        evidence["expected_pid"] = child.pid
        for label, access in [("success", bridge.PROCESS_QUERY_LIMITED_INFORMATION),
                              ("query_denied", bridge.SYNCHRONIZE)]:
            handle = kernel.OpenProcess(access, False, child.pid)
            assert handle
            # Ownership transfers to the production helper, never close it again here.
            if label == "success":
                actual_pid = bridge.consume_organizer_process_handle(handle)
                assert actual_pid == child.pid
                evidence[label] = {"handle": handle, "actual_pid": actual_pid}
            else:
                with pytest.raises(OSError) as caught:
                    bridge.consume_organizer_process_handle(handle)
                assert caught.value.errno == 5
                evidence[label] = {"handle": handle, "error": caught.value.errno}
            flags = ctypes.c_uint32()
            ctypes.set_last_error(0)
            assert kernel.GetHandleInformation(handle, ctypes.byref(flags)) == 0
            assert ctypes.get_last_error() == 6  # ERROR_INVALID_HANDLE proves release.
            evidence[label]["released_error"] = ctypes.get_last_error()
    finally:
        # Only this test's child; it normally exits itself within one second.
        try:
            evidence["child_exit_code"] = child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait(timeout=5)
            raise
        (tmp_path / "handle-readback.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    assert evidence["child_exit_code"] == 0
    print(json.dumps(evidence))

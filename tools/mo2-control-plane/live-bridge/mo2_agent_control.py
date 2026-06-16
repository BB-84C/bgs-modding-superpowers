"""MO2 live bootstrap bridge.

This module lives at `<MO2_Root>/plugins/mo2_agent_control.py` once deployed.
Runtime files stay under `<MO2_Root>/plugins/Mo2AgentControl/bootstrap/runtime`.
It now exposes `createPlugin()` so MO2 can load it as a real Python plugin.
Bootstrap runtime publication happens during plugin initialization, not at import.
File-bootstrap is retained only as discovery and liveness, not as the command transport.
"""

from __future__ import annotations

import ctypes
import configparser as _configparser
import json
import logging
import os
import queue
import re as _re
import subprocess
import tempfile as _tempfile
import threading
import time
import uuid
from datetime import datetime, timezone
from io import StringIO as _StringIO
from pathlib import Path

import mobase


log = logging.getLogger(__name__)


try:
    from mobase import ModState as _ModState

    try:
        _ACTIVE_FLAG = int(_ModState.active)
    except AttributeError:
        _ACTIVE_FLAG = int(_ModState.ACTIVE)
except (ImportError, AttributeError):
    # Fallback when running under unit tests without mobase loaded.
    _ACTIVE_FLAG = 2  # ModState::Active = 2 per MO2 source.

try:
    from mobase import GuessedString
except ImportError:
    # Unit tests patch this symbol; runtime should provide mobase.GuessedString.
    GuessedString = None


# Canonical error codes (match broker-schema.json#/definitions/errorCode)
class ErrorCode:
    INVALID_REQUEST = "invalid_request"
    METHOD_NOT_FOUND = "method_not_found"
    INVALID_PARAMS = "invalid_params"
    TRANSPORT_ERROR = "transport_error"
    NOT_IMPLEMENTED = "not_implemented"
    INTERNAL_ERROR = "internal_error"
    MOD_NOT_FOUND = "mod_not_found"
    PRIORITY_OUT_OF_RANGE = "priority_out_of_range"
    PLUGIN_NOT_FOUND = "plugin_not_found"
    REFRESH_TIMEOUT = "refresh_timeout"
    MAIN_THREAD_UNAVAILABLE = "main_thread_unavailable"
    MO2_SHUTTING_DOWN = "mo2_shutting_down"


# Post-response hook registry (FIFO; fires after pipe response is written + flushed,
# before DisconnectNamedPipe). Used by system.shutdown to enqueue QCoreApplication.quit()
# only AFTER the success ack reaches the client.
_post_response_hooks: list = []


def register_post_response_hook(callable_):
    _post_response_hooks.append(callable_)


def drain_post_response_hooks():
    while _post_response_hooks:
        hook = _post_response_hooks.pop(0)
        try:
            hook()
        except Exception as exc:
            log.warning(f"post-response hook error: {exc}")


PLUGIN_NAME = "Mo2AgentControl"
PLUGIN_SOURCE_SUBTREE = "tools/mo2-control-plane/live-bridge/"
# Deployment targets are relative to the user's MO2 root, supplied by the
# installer (scripts/install-mo2-control-plane.ps1). The dev sandbox is no
# longer assumed.
PLUGIN_DEPLOYMENT_TARGET = "plugins/mo2_agent_control.py"
PLUGIN_SUPPORT_TARGET = "plugins/Mo2AgentControl/"
BOOTSTRAP_MODE = "file-bootstrap"
BOOTSTRAP_DIRECTORY_NAME = "bootstrap"
RUNTIME_DIRECTORY_NAME = "runtime"

RUNTIME_SCHEMA_VERSION = 1
RUNTIME_READY_STATE = "ok"
RUNTIME_TRANSPORT = "named-pipe"
RUNTIME_ENDPOINT_FIELD = "endpoint"
RUNTIME_PIPE_NAME_PREFIX = "mo2-control-plane-"
RUNTIME_PIPE_NAME_OVERRIDE = None

RUNTIME_STATUS_FILE = "status.json"
RUNTIME_CAPABILITIES_FILE = "capabilities.json"
RUNTIME_ENDPOINT_FILE = "endpoint.json"
BLOCKER_EVENTS_FILE = "blocker-events.jsonl"
PROTOCOL_VERSION = "1"

KNOWN_BLOCKER_DIALOGS = (
    {
        "type": "unlock",
        "title": "ModOrganizer",
        "textPrefix": "Mod Organizer is locked while the application is running.\n",
        "buttons": ("Unlock",),
    },
    {
        "type": "exit-now",
        "title": "ModOrganizer",
        "textPrefix": "Mod Organizer is waiting on an application to close before exiting.\n",
        "buttons": ("Exit Now", "Cancel"),
    },
)

NAMED_PIPE_BUFFER_SIZE = 4096
NAMED_PIPE_PREFIX = "\\\\.\\pipe\\"

PIPE_ACCESS_DUPLEX = 0x00000003
PIPE_TYPE_BYTE = 0x00000000
PIPE_READMODE_BYTE = 0x00000000
PIPE_WAIT = 0x00000000
PIPE_UNLIMITED_INSTANCES = 255

ERROR_BROKEN_PIPE = 109
ERROR_NO_DATA = 232
ERROR_PIPE_CONNECTED = 535
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
INFINITE = 0xFFFFFFFF
STILL_ACTIVE = 259

PROCESS_TERMINATE = 0x0001
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
SYNCHRONIZE = 0x00100000

INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)

KERNEL32.CreateNamedPipeW.argtypes = [
    ctypes.c_wchar_p,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_uint32,
    ctypes.c_void_p,
]
KERNEL32.CreateNamedPipeW.restype = ctypes.c_void_p

KERNEL32.OpenProcess.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32]
KERNEL32.OpenProcess.restype = ctypes.c_void_p

KERNEL32.ConnectNamedPipe.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
KERNEL32.ConnectNamedPipe.restype = ctypes.c_int

KERNEL32.ReadFile.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_void_p,
]
KERNEL32.ReadFile.restype = ctypes.c_int

KERNEL32.WriteFile.argtypes = [
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_uint32,
    ctypes.POINTER(ctypes.c_uint32),
    ctypes.c_void_p,
]
KERNEL32.WriteFile.restype = ctypes.c_int

KERNEL32.FlushFileBuffers.argtypes = [ctypes.c_void_p]
KERNEL32.FlushFileBuffers.restype = ctypes.c_int

KERNEL32.DisconnectNamedPipe.argtypes = [ctypes.c_void_p]
KERNEL32.DisconnectNamedPipe.restype = ctypes.c_int

KERNEL32.CloseHandle.argtypes = [ctypes.c_void_p]
KERNEL32.CloseHandle.restype = ctypes.c_int

KERNEL32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
KERNEL32.WaitForSingleObject.restype = ctypes.c_uint32

KERNEL32.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
KERNEL32.GetExitCodeProcess.restype = ctypes.c_int

KERNEL32.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
KERNEL32.TerminateProcess.restype = ctypes.c_int

_ACTIVE_NAMED_PIPE_TRANSPORTS: list[dict[str, object]] = []
_SEEN_BLOCKER_DIALOG_FINGERPRINTS: dict[str, set[str]] = {
    "handled": set(),
    "ignored": set(),
    "failed": set(),
}


class MainThreadCall:
    """Represent one callable scheduled onto the plugin main thread."""

    def __init__(self, callback) -> None:
        self.callback = callback
        self.completed = threading.Event()
        self.result = None
        self.error = None


class MainThreadCallPump:
    """Queue cross-thread work and execute it when the main thread pumps."""

    def __init__(self) -> None:
        self._owner_thread_id = threading.get_ident()
        self._calls: queue.Queue[MainThreadCall] = queue.Queue()

    def enqueue(self, callback) -> MainThreadCall:
        """Queue work for the owning thread without blocking the caller."""

        call = MainThreadCall(callback)
        self._calls.put(call)
        return call

    def invoke(self, callback):
        """Run work on the owning thread, blocking callers from other threads."""

        if threading.get_ident() == self._owner_thread_id:
            return callback()

        call = MainThreadCall(callback)
        self._calls.put(call)
        call.completed.wait()
        if call.error is not None:
            raise call.error

        return call.result

    def invoke_blocking(self, callback, timeout_s: float = 10):
        """Run work on the owning thread; timeout is reserved for future pump waits."""

        return self.invoke(callback)

    def pending_count(self) -> int:
        """Return the approximate number of queued main-thread calls."""

        return self._calls.qsize()

    def pump_once(self, timeout_seconds: float = 0.0) -> bool:
        """Execute at most one queued call on the owning thread."""

        if timeout_seconds > 0:
            try:
                call = self._calls.get(timeout=timeout_seconds)
            except queue.Empty:
                return False
        else:
            try:
                call = self._calls.get_nowait()
            except queue.Empty:
                return False

        try:
            call.result = call.callback()
        except Exception as exc:  # pragma: no cover - surfaced to the waiting caller.
            call.error = exc
        finally:
            call.completed.set()

        return True

    def pump_all(self) -> int:
        """Drain all queued calls from the owning thread."""

        pumped = 0
        while self.pump_once():
            pumped += 1

        return pumped


_main_thread_pump: MainThreadCallPump | None = None


def _set_main_thread_pump(main_thread_pump: MainThreadCallPump | None) -> None:
    global _main_thread_pump
    if main_thread_pump is not None:
        _main_thread_pump = main_thread_pump


def _get_main_thread_pump() -> MainThreadCallPump:
    if _main_thread_pump is None:
        raise RuntimeError("main-thread pump is unavailable")

    return _main_thread_pump


RUNTIME_FILE_NAMES = (
    RUNTIME_STATUS_FILE,
    RUNTIME_CAPABILITIES_FILE,
    RUNTIME_ENDPOINT_FILE,
)

SYSTEM_PING_METHOD = "system.ping"
SYSTEM_CAPABILITIES_METHOD = "system.capabilities"
SYSTEM_SHUTDOWN_METHOD = "system.shutdown"
MODS_LIST_METHOD = "mods.list"
MODS_SET_ACTIVE_METHOD = "mods.set_active"
MODS_SET_PRIORITY_METHOD = "mods.set_priority"
MODS_RENAME_METHOD = "mods.rename"
MODS_REMOVE_METHOD = "mods.remove"
MODS_CREATE_METHOD = "mods.create"
MODS_META_READ_METHOD = "mods.meta_read"
MODS_META_WRITE_METHOD = "mods.meta_write"
PLUGINS_LIST_METHOD = "plugins.list"
PLUGINS_SET_STATE_METHOD = "plugins.set_state"
PLUGINS_SET_PRIORITY_METHOD = "plugins.set_priority"
PLUGINS_SET_LOAD_ORDER_METHOD = "plugins.set_load_order"
PROFILE_LIST_METHOD = "profile.list"
PROFILE_ACTIVE_METHOD = "profile.active"
PROFILE_INITIALIZE_METHOD = "profile.initialize"
EXECUTABLES_LIST_METHOD = "executables.list"
INSTALLATION_INSTALL_LOCAL_ARCHIVE_METHOD = "installation.install_local_archive"
INSTALLATION_CREATE_MOD_FROM_DIRECTORY_METHOD = "installation.create_mod_from_directory"
ORGANIZER_REFRESH_METHOD = "organizer.refresh"
ORGANIZER_RESOLVE_PATH_METHOD = "organizer.resolve_path"
ORGANIZER_GET_FILE_ORIGINS_METHOD = "organizer.get_file_origins"
ORGANIZER_FIND_FILES_METHOD = "organizer.find_files"
ORGANIZER_VIRTUAL_FILE_TREE_METHOD = "organizer.virtual_file_tree"
ORGANIZER_START_APPLICATION_METHOD = "organizer.start_application"
ORGANIZER_WAIT_FOR_APPLICATION_METHOD = "organizer.wait_for_application"

_INVALID_PATH_CHARS = _re.compile(r'[<>:"/\\|?*\x00-\x1f]')

LAUNCH_START_METHOD = "launch.start"
LAUNCH_STATUS_METHOD = "launch.status"
LAUNCH_WAIT_METHOD = "launch.wait"
LAUNCH_STOP_METHOD = "launch.stop"

LAUNCH_METHODS = (
    LAUNCH_START_METHOD,
    LAUNCH_STATUS_METHOD,
    LAUNCH_WAIT_METHOD,
    LAUNCH_STOP_METHOD,
)

LAUNCH_REGISTRY_ENTRIES_FIELD = "launches"
LAUNCH_REGISTRY_ENTRY_FIELDS = (
    "launch_id",
    "session_id",
    "target_path",
    "args",
    "cwd",
    "env",
    "pid",
    "process_handle",
    "status",
    "started_at",
    "updated_at",
    "exit_code",
    "artifacts",
)
LAUNCH_REGISTRY_STATUS_PENDING = "pending"
LAUNCH_REGISTRY_STATUS_RUNNING = "running"
LAUNCH_REGISTRY_STATUS_COMPLETED = "completed"
LAUNCH_REGISTRY_STATUS_STOPPED = "stopped"
LAUNCH_REGISTRY_STATUS_VALUES = (
    LAUNCH_REGISTRY_STATUS_PENDING,
    LAUNCH_REGISTRY_STATUS_RUNNING,
    LAUNCH_REGISTRY_STATUS_COMPLETED,
    LAUNCH_REGISTRY_STATUS_STOPPED,
)
TERMINAL_LAUNCH_RETENTION_LIMIT = 32

LAUNCH_COMMAND_CONTRACTS = {
    LAUNCH_START_METHOD: {
        "payloadFields": ("target_path", "args", "cwd", "env"),
        "resultFields": ("launch_id", "pid", "status", "started_at", "artifacts"),
    },
    LAUNCH_STATUS_METHOD: {
        "payloadFields": ("launch_id",),
        "resultFields": ("launch_id", "pid", "status"),
    },
    LAUNCH_WAIT_METHOD: {
        "payloadFields": ("launch_id",),
        "resultFields": ("launch_id", "pid", "status"),
    },
    LAUNCH_STOP_METHOD: {
        "payloadFields": ("launch_id",),
        "resultFields": ("launch_id", "pid", "status"),
    },
}

MINIMUM_RUNTIME_JSON_FIELDS = {
    RUNTIME_STATUS_FILE: ("schemaVersion", "state", "mo2Pid"),
    RUNTIME_CAPABILITIES_FILE: ("schemaVersion", "methods"),
    RUNTIME_ENDPOINT_FILE: ("schemaVersion", "transport", RUNTIME_ENDPOINT_FIELD),
}


def build_transport_response(
    request: dict[str, object],
    *,
    ok: bool,
    result: dict[str, object] | None = None,
    error: dict[str, object] | None = None,
) -> dict[str, object]:
    """Shape Python transport responses to match broker envelopes."""

    return {
        "protocol_version": request.get("protocol_version", PROTOCOL_VERSION),
        "request_id": request.get("request_id"),
        "session_id": request.get("session_id"),
        "ok": ok,
        "result": result,
        "error": error,
    }


def is_broker_handler_response(value: object) -> bool:
    """Return True when a command handler already returned a broker envelope."""

    return (
        isinstance(value, dict)
        and isinstance(value.get("ok"), bool)
        and "result" in value
        and "error" in value
    )


def get_named_pipe_path(pipe_name: str) -> str:
    """Return a Windows named-pipe path from a configured endpoint value."""

    if pipe_name.startswith(NAMED_PIPE_PREFIX):
        return pipe_name

    return f"{NAMED_PIPE_PREFIX}{pipe_name}"


def get_runtime_pipe_name(process_id: int | None = None) -> str:
    """Return an instance-specific pipe name for the current MO2 process."""

    if RUNTIME_PIPE_NAME_OVERRIDE:
        return str(RUNTIME_PIPE_NAME_OVERRIDE)

    resolved_process_id = os.getpid() if process_id is None else int(process_id)
    return f"{RUNTIME_PIPE_NAME_PREFIX}{resolved_process_id}"


def raise_last_windows_error(prefix: str) -> None:
    """Raise an OSError with the current Windows error state."""

    error_code = ctypes.get_last_error()
    error_message = ctypes.FormatError(error_code).strip()
    raise OSError(error_code, f"{prefix}: {error_message}")


def create_named_pipe_handle(pipe_path: str):
    """Create a single duplex named-pipe instance."""

    handle = KERNEL32.CreateNamedPipeW(
        pipe_path,
        PIPE_ACCESS_DUPLEX,
        PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
        PIPE_UNLIMITED_INSTANCES,
        NAMED_PIPE_BUFFER_SIZE,
        NAMED_PIPE_BUFFER_SIZE,
        0,
        None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise_last_windows_error(f"Failed to create named pipe {pipe_path}")

    return handle


def read_named_pipe_message(pipe_handle) -> dict[str, object] | None:
    """Read one newline-delimited JSON request from a connected pipe."""

    chunks = bytearray()
    while True:
        buffer = ctypes.create_string_buffer(NAMED_PIPE_BUFFER_SIZE)
        bytes_read = ctypes.c_uint32()
        success = KERNEL32.ReadFile(
            pipe_handle,
            buffer,
            NAMED_PIPE_BUFFER_SIZE,
            ctypes.byref(bytes_read),
            None,
        )
        if not success:
            error_code = ctypes.get_last_error()
            if error_code in (ERROR_BROKEN_PIPE, ERROR_NO_DATA):
                break

            raise_last_windows_error("Failed to read named-pipe request")

        if bytes_read.value == 0:
            break

        chunks.extend(buffer.raw[: bytes_read.value])
        if b"\n" in chunks:
            break

    if not chunks:
        return None

    raw_message = chunks.split(b"\n", 1)[0].strip()
    if not raw_message:
        return None

    return json.loads(raw_message.decode("utf-8"))


def write_named_pipe_message(pipe_handle, message: dict[str, object]) -> None:
    """Write one newline-delimited JSON response to a connected pipe."""

    encoded_message = (json.dumps(message) + "\n").encode("utf-8")
    offset = 0
    while offset < len(encoded_message):
        chunk = encoded_message[offset:]
        bytes_written = ctypes.c_uint32()
        success = KERNEL32.WriteFile(
            pipe_handle,
            ctypes.c_char_p(chunk),
            len(chunk),
            ctypes.byref(bytes_written),
            None,
        )
        if not success:
            raise_last_windows_error("Failed to write named-pipe response")

        offset += bytes_written.value


def build_invalid_request_response(exc: json.JSONDecodeError) -> dict[str, object]:
    """Return a transport error envelope for malformed JSON requests."""

    return build_transport_response(
        {},
        ok=False,
        error={
            "code": ErrorCode.INVALID_REQUEST,
            "message": str(exc),
        },
    )


def import_qt_core_module():
    """Import a QtCore module compatible with the MO2 Python host."""

    for module_name in ("PyQt6.QtCore", "PyQt5.QtCore"):
        try:
            module = __import__(module_name, fromlist=["QCoreApplication", "QTimer"])
        except ImportError:
            continue

        if hasattr(module, "QCoreApplication") and hasattr(module, "QTimer"):
            return module

    raise RuntimeError("Organizer-backed launches require PyQt5/PyQt6 QtCore for main-thread pumping")


def import_qt_widgets_module():
    """Import a QtWidgets module compatible with the MO2 Python host."""

    for module_name in ("PyQt6.QtWidgets", "PyQt5.QtWidgets"):
        try:
            module = __import__(module_name, fromlist=["QApplication", "QDialog", "QPushButton"])
        except ImportError:
            continue

        if all(hasattr(module, name) for name in ("QApplication", "QDialog", "QPushButton")):
            return module

    raise RuntimeError("Blocker dialog watcher requires PyQt5/PyQt6 QtWidgets")


def extract_dialog_snapshot(dialog):
    """Return the normalized snapshot used for whitelist matching."""

    qt_widgets = import_qt_widgets_module()
    buttons = [str(button.text()) for button in dialog.findChildren(qt_widgets.QPushButton)]
    return {
        "title": str(dialog.windowTitle() or ""),
        "text": str(dialog.text() or ""),
        "buttons": buttons,
    }


def find_button_by_text(dialog, expected_text):
    """Return the first dialog button with an exact text match."""

    qt_widgets = import_qt_widgets_module()
    for button in dialog.findChildren(qt_widgets.QPushButton):
        if str(button.text()) == str(expected_text):
            return button

    return None


def is_dialog_candidate(dialog):
    """Return True only for visible top-level Qt dialogs."""

    qt_widgets = import_qt_widgets_module()
    if not isinstance(dialog, qt_widgets.QDialog):
        return False

    try:
        if not bool(dialog.isVisible()):
            return False
    except Exception:
        return False

    for attribute_name in ("windowTitle", "text", "findChildren"):
        try:
            attribute = getattr(dialog, attribute_name)
        except Exception:
            return False

        if not callable(attribute):
            return False

    return True


def build_dialog_fingerprint(snapshot):
    """Build a stable fingerprint for one dialog appearance."""

    return json.dumps(
        {
            "title": str(snapshot.get("title") or ""),
            "text": str(snapshot.get("text") or ""),
            "buttons": [str(button) for button in list(snapshot.get("buttons") or [])],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def create_blocker_event(snapshot, *, result: str, source: str, matched_dialog=None):
    """Build one persisted blocker-event record from a dialog snapshot."""

    event = {
        "type": str((matched_dialog or {}).get("type") or result),
        "title": str(snapshot.get("title") or ""),
        "text": str(snapshot.get("text") or ""),
        "buttons": [str(button) for button in list(snapshot.get("buttons") or [])],
        "result": str(result),
        "source": str(source),
    }
    if matched_dialog is not None and matched_dialog.get("type") is not None:
        event["matchedType"] = str(matched_dialog["type"])

    return event


def handle_known_blocker_dialog(dialog, runtime_root=None) -> str:
    """Click the whitelisted blocker dialog action button once when matched."""

    snapshot = extract_dialog_snapshot(dialog)
    matched_dialog = match_blocker_dialog(snapshot["title"], snapshot["text"], snapshot["buttons"])
    if matched_dialog is None:
        append_blocker_event(
            runtime_root,
            create_blocker_event(snapshot, result="ignored", source="candidate-dialog"),
        )
        return "ignored"

    expected_button_text = matched_dialog["buttons"][0]
    button = find_button_by_text(dialog, expected_button_text)
    if button is None:
        append_blocker_event(
            runtime_root,
            create_blocker_event(
                snapshot,
                result="failed",
                source="matched-dialog",
                matched_dialog=matched_dialog,
            ),
        )
        return "failed"

    try:
        button.click()
    except Exception:
        append_blocker_event(
            runtime_root,
            create_blocker_event(
                snapshot,
                result="failed",
                source="matched-dialog",
                matched_dialog=matched_dialog,
            ),
        )
        return "failed"

    append_blocker_event(
        runtime_root,
        create_blocker_event(
            snapshot,
            result="handled",
            source="matched-dialog",
            matched_dialog=matched_dialog,
        ),
    )
    return "handled"


def scan_for_known_blocker_dialogs(runtime_root=None) -> int:
    """Scan visible top-level dialogs and handle strict whitelist matches only once per appearance."""

    qt_widgets = import_qt_widgets_module()
    application = qt_widgets.QApplication.instance()
    if application is None:
        return 0

    current_fingerprints = set()
    handled_count = 0
    outcome_groups = tuple(_SEEN_BLOCKER_DIALOG_FINGERPRINTS.values())
    for widget in application.topLevelWidgets():
        if not is_dialog_candidate(widget):
            continue

        snapshot = extract_dialog_snapshot(widget)
        fingerprint = build_dialog_fingerprint(snapshot)
        current_fingerprints.add(fingerprint)
        if any(fingerprint in fingerprints for fingerprints in outcome_groups):
            continue

        outcome = handle_known_blocker_dialog(widget, runtime_root=runtime_root)
        if outcome == "handled":
            _SEEN_BLOCKER_DIALOG_FINGERPRINTS["handled"].add(fingerprint)
            handled_count += 1
        elif outcome == "failed":
            _SEEN_BLOCKER_DIALOG_FINGERPRINTS["failed"].add(fingerprint)
        else:
            _SEEN_BLOCKER_DIALOG_FINGERPRINTS["ignored"].add(fingerprint)

    for outcome_name, fingerprints in _SEEN_BLOCKER_DIALOG_FINGERPRINTS.items():
        _SEEN_BLOCKER_DIALOG_FINGERPRINTS[outcome_name] = fingerprints.intersection(current_fingerprints)

    return handled_count


def install_blocker_watcher_timer(runtime_root=None, interval_ms=100):
    """Install a Qt timer that scans for whitelisted blocker dialogs."""

    qt_core = import_qt_core_module()
    application = qt_core.QCoreApplication.instance()
    timer = qt_core.QTimer(application) if application is not None else qt_core.QTimer()
    timer.setInterval(interval_ms)
    timer.timeout.connect(lambda: scan_for_known_blocker_dialogs(runtime_root=runtime_root))
    timer.start()
    return timer


def install_main_thread_pump_timer(main_thread_pump: MainThreadCallPump, interval_ms: int = 10):
    """Install a Qt timer that drains queued calls on the plugin main thread."""

    qt_core = import_qt_core_module()
    application = qt_core.QCoreApplication.instance()
    timer = qt_core.QTimer(application) if application is not None else qt_core.QTimer()
    timer.setInterval(interval_ms)
    timer.timeout.connect(main_thread_pump.pump_all)
    timer.start()
    return timer


def serve_named_pipe_requests(pipe_name: str, handlers, stop_event: threading.Event) -> None:
    """Serve one JSON request per connection on a background thread."""

    pipe_path = get_named_pipe_path(pipe_name)
    while not stop_event.is_set():
        pipe_handle = create_named_pipe_handle(pipe_path)
        client_thread = None
        try:
            connected = KERNEL32.ConnectNamedPipe(pipe_handle, None)
            if not connected:
                error_code = ctypes.get_last_error()
                if error_code != ERROR_PIPE_CONNECTED:
                    raise_last_windows_error(f"Failed to accept named-pipe client for {pipe_path}")
            client_thread = threading.Thread(
                target=serve_named_pipe_client,
                args=(pipe_handle, handlers),
                name=f"{PLUGIN_NAME}-named-pipe-client",
                daemon=True,
            )
            client_thread.start()
            pipe_handle = None
        finally:
            if pipe_handle is not None:
                KERNEL32.DisconnectNamedPipe(pipe_handle)
                KERNEL32.CloseHandle(pipe_handle)


def serve_named_pipe_client(pipe_handle, handlers) -> None:
    """Handle one connected client without blocking the accept loop."""

    try:
        try:
            request = read_named_pipe_message(pipe_handle)
        except json.JSONDecodeError as exc:
            write_named_pipe_message(pipe_handle, build_invalid_request_response(exc))
            KERNEL32.FlushFileBuffers(pipe_handle)
            drain_post_response_hooks()
            return

        if request is None:
            return

        try:
            response = dispatch_transport_request(request, handlers)
        except json.JSONDecodeError as exc:
            response = build_invalid_request_response(exc)

        write_named_pipe_message(pipe_handle, response)
        KERNEL32.FlushFileBuffers(pipe_handle)
        drain_post_response_hooks()
    finally:
        KERNEL32.DisconnectNamedPipe(pipe_handle)
        KERNEL32.CloseHandle(pipe_handle)


def handle_system_ping(_request: dict[str, object]) -> dict[str, object]:
    """Return the minimal plugin-local liveness payload."""

    return {
        "status": RUNTIME_READY_STATE,
    }


def _handle_system_shutdown(organizer, payload):
    """Shutdown MO2 cleanly after the success ack reaches the client.

    Ordering contract (PLAN-PATCH P-B2):
    1. Handler returns success dict immediately.
    2. dispatch_transport_request wraps + serve_named_pipe_client writes + FlushFileBuffers.
    3. drain_post_response_hooks() runs and enqueues QCoreApplication.quit() on the main thread pump.
    4. DisconnectNamedPipe closes the pipe.
    """

    pump = _get_main_thread_pump()

    def enqueue_quit():
        qt_core = import_qt_core_module()
        pump.enqueue(lambda: qt_core.QCoreApplication.quit())

    register_post_response_hook(enqueue_quit)
    return {"ok": True, "result": {"shutting_down": True}, "error": None}


def _handle_mods_list(organizer, payload):
    """Background-safe snapshot of all mods with priority + enabled + separator flag.

    P-F4: uses mobase ModState.active when available, falls back to 2.
    P-F5: separator detection prefers IModInterface.isSeparator(), falling back
    to the conventional *_separator suffix only when the live API is unavailable.
    """

    mod_list = organizer.modList()
    mods = []
    for name in mod_list.allMods():
        state = mod_list.state(name)
        try:
            mod = mod_list.getMod(name)
            is_separator = bool(mod.isSeparator()) if mod is not None else name.endswith("_separator")
        except Exception:
            is_separator = name.endswith("_separator")

        mods.append(
            {
                "name": name,
                "priority": mod_list.priority(name),
                "enabled": bool(state & _ACTIVE_FLAG),
                "is_separator": is_separator,
            }
        )

    return {"ok": True, "result": {"mods": mods}, "error": None}


def _handle_mods_set_active(organizer, pump, payload):
    """Set mod active state via main-thread mobase. Bulk + readback.

    Per oracle traps §2.2: bulk setActive returns count; per-mod readback
    confirms actual state and catches partial-apply / silent-noop behavior.
    """

    names = payload.get("names")
    active = payload.get("active")
    if not isinstance(names, list) or not all(isinstance(name, str) for name in names):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "names: list[str]"},
        }
    if not isinstance(active, bool):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "active: bool"},
        }

    def _on_main_thread():
        mod_list = organizer.modList()
        try:
            mod_list.setActive(names, active)
        except (TypeError, AttributeError):
            for name in names:
                try:
                    mod_list.setActive(name, active)
                except Exception:
                    pass

        applied = []
        failed = []
        readback = []
        for name in names:
            try:
                state = mod_list.state(name)
                is_active_now = bool(state & _ACTIVE_FLAG)
                readback.append({"name": name, "active": is_active_now})
                if is_active_now == active:
                    applied.append(name)
                else:
                    failed.append(name)
            except Exception:
                readback.append({"name": name, "active": None})
                failed.append(name)

        return {
            "requested": list(names),
            "applied": applied,
            "failed": failed,
            "readback": readback,
        }

    try:
        result = pump.invoke_blocking(_on_main_thread, timeout_s=10)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    return {"ok": True, "result": result, "error": None}


def _handle_mods_set_priority(organizer, pump, payload):
    """Reorder a mod via main-thread setPriority + readback.

    oracle §2.1: setPriority can silently no-op when master/non-master
    inversion would be required. Readback exposes this via noop=true.
    """

    name = payload.get("name")
    priority = payload.get("priority")
    if not isinstance(name, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "name: str"},
        }
    if not isinstance(priority, int) or isinstance(priority, bool):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "priority: int"},
        }

    def _on_main_thread():
        mod_list = organizer.modList()
        if mod_list.getMod(name) is None:
            return ("error", ErrorCode.MOD_NOT_FOUND, f"mod '{name}' not found")

        all_mods = list(mod_list.allMods())
        non_separator_mods = [mod_name for mod_name in all_mods if not mod_name.endswith("_separator")]
        max_priority = max(0, len(non_separator_mods))
        if priority < 0 or priority > max_priority:
            return (
                "error",
                ErrorCode.PRIORITY_OUT_OF_RANGE,
                f"priority {priority} out of [0..{max_priority}]",
            )

        before = mod_list.priority(name)
        mod_list.setPriority(name, priority)
        actual = mod_list.priority(name)
        return (
            "ok",
            {
                "name": name,
                "requested_priority": priority,
                "actual_priority": actual,
                "noop": (actual == before) and (before != priority),
            },
        )

    try:
        outcome = pump.invoke_blocking(_on_main_thread, timeout_s=10)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    if outcome[0] == "error":
        return {
            "ok": False,
            "result": None,
            "error": {"code": outcome[1], "message": outcome[2]},
        }

    return {"ok": True, "result": outcome[1], "error": None}


def _sanitize_dir_name(name: str) -> str:
    """Strip illegal path chars before MO2 can raise a blocking Qt dialog.

    This mirrors MO2's fixDirectoryName behavior closely enough for the broker:
    remove path-invalid characters, trim leading/trailing whitespace, then remove
    trailing dots before calling renameMod (oracle §A4).
    """

    return _INVALID_PATH_CHARS.sub("", name).strip().rstrip(".")


def _handle_mods_rename(organizer, pump, payload):
    """Rename a mod via main-thread renameMod, pre-sanitized + collision-checked."""

    old_name = payload.get("old_name")
    new_name = payload.get("new_name")
    if not isinstance(old_name, str) or not isinstance(new_name, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "old_name + new_name: str"},
        }

    sanitized_name = _sanitize_dir_name(new_name)
    if not sanitized_name:
        return {
            "ok": False,
            "result": None,
            "error": {
                "code": ErrorCode.INVALID_PARAMS,
                "message": f"new_name '{new_name}' empty after sanitize",
            },
        }

    def _on_main_thread():
        mod_list = organizer.modList()
        mod = mod_list.getMod(old_name)
        if mod is None:
            return ("error", ErrorCode.MOD_NOT_FOUND, f"mod '{old_name}' not found")

        if sanitized_name != old_name and mod_list.getMod(sanitized_name) is not None:
            return ("error", ErrorCode.INVALID_PARAMS, f"name '{sanitized_name}' already exists")

        refreshed = mod_list.renameMod(mod, sanitized_name)
        return (
            "ok",
            {
                "old_name": old_name,
                "new_name": refreshed.name() if refreshed is not None else sanitized_name,
                "name_was_sanitized": sanitized_name != new_name,
            },
        )

    try:
        outcome = pump.invoke_blocking(_on_main_thread, timeout_s=15)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    if outcome[0] == "error":
        return {
            "ok": False,
            "result": None,
            "error": {"code": outcome[1], "message": outcome[2]},
        }

    return {"ok": True, "result": outcome[1], "error": None}


def _handle_mods_remove(organizer, pump, payload):
    """Remove a mod via main-thread IModList.removeMod.

    Destructive primitive: removeMod can physically delete files. Per oracle §A6,
    callers should pair this command with backup orchestration at the MCP layer.
    """

    name = payload.get("name")
    if not isinstance(name, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "name: str"},
        }

    def _on_main_thread():
        mod_list = organizer.modList()
        mod = mod_list.getMod(name)
        if mod is None:
            return ("error", ErrorCode.MOD_NOT_FOUND, f"mod '{name}' not found")

        removed = mod_list.removeMod(mod)
        if not removed:
            return ("error", ErrorCode.INTERNAL_ERROR, "removeMod returned False")

        return ("ok", {"name": name, "removed": True})

    try:
        outcome = pump.invoke_blocking(_on_main_thread, timeout_s=30)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    if outcome[0] == "error":
        return {
            "ok": False,
            "result": None,
            "error": {"code": outcome[1], "message": outcome[2]},
        }

    return {"ok": True, "result": outcome[1], "error": None}


def _handle_mods_create(organizer, pump, payload):
    """Create an empty mod via createMod + optional setPriority + notification.

    Per oracle §A1, MO2 GUI creates at default priority then reorders. This
    broker primitive composes those steps and emits the resulting priority.
    """

    name = payload.get("name")
    target_priority = payload.get("priority")
    if not isinstance(name, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "name: str"},
        }
    if target_priority is not None and (not isinstance(target_priority, int) or isinstance(target_priority, bool)):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "priority: int"},
        }

    sanitized_name = _sanitize_dir_name(name)
    if not sanitized_name:
        return {
            "ok": False,
            "result": None,
            "error": {
                "code": ErrorCode.INVALID_PARAMS,
                "message": f"name '{name}' empty after sanitize",
            },
        }

    def _on_main_thread():
        mod_list = organizer.modList()
        if mod_list.getMod(sanitized_name) is not None:
            return ("error", ErrorCode.INVALID_PARAMS, f"name '{sanitized_name}' already exists")
        if GuessedString is None:
            return ("error", ErrorCode.INTERNAL_ERROR, "mobase.GuessedString unavailable")

        new_mod = organizer.createMod(GuessedString(sanitized_name))
        if new_mod is None:
            return ("error", ErrorCode.INTERNAL_ERROR, "createMod returned None")

        actual_name = new_mod.name()
        # Defensive: ensure the mod folder is materialized on disk before this
        # call returns. organizer.createMod() registers the mod in MO2's model
        # but does not guarantee the directory exists until the next save cycle;
        # downstream MCP tools (mo2_remove_mod buildPlan, mo2_assets_resolve,
        # etc.) check the filesystem and would race against the broker if the
        # folder were only in-memory. absolute_path is also surfaced so the
        # MCP layer does not need to re-resolve mod_directory.
        absolute_path = new_mod.absolutePath()
        try:
            os.makedirs(absolute_path, exist_ok=True)
        except OSError:
            # Tolerate races / readonly mounts; downstream callers will surface
            # any real filesystem error when they try to use the path.
            pass

        result = {
            "name": actual_name,
            "created": True,
            "priority": mod_list.priority(actual_name),
            "absolute_path": absolute_path,
        }
        if target_priority is not None:
            mod_list.setPriority(actual_name, target_priority)
            result["priority"] = mod_list.priority(actual_name)
            result["requested_priority"] = target_priority

        organizer.modDataChanged(new_mod)
        return ("ok", result)

    try:
        outcome = pump.invoke_blocking(_on_main_thread, timeout_s=15)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    if outcome[0] == "error":
        return {
            "ok": False,
            "result": None,
            "error": {"code": outcome[1], "message": outcome[2]},
        }

    return {"ok": True, "result": outcome[1], "error": None}


def _handle_mods_meta_read(organizer, payload):
    """Read a mod's meta.ini fields. Background-safe pure file read."""

    name = payload.get("name")
    if not isinstance(name, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "name: str"},
        }

    mod_list = organizer.modList()
    mod = mod_list.getMod(name)
    if mod is None:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MOD_NOT_FOUND, "message": name},
        }

    meta_path = Path(mod.absolutePath()) / "meta.ini"
    if not meta_path.exists():
        return {
            "ok": True,
            "result": {"name": name, "meta": {}, "exists": False},
            "error": None,
        }

    parser = _configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    try:
        parser.read(meta_path, encoding="utf-8")
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INTERNAL_ERROR, "message": f"meta.ini parse failed: {exc}"},
        }

    meta = {section: dict(parser[section]) for section in parser.sections()}
    return {
        "ok": True,
        "result": {"name": name, "meta": meta, "exists": True},
        "error": None,
    }


def _atomic_write_text_inline(path: Path, content: str) -> None:
    """Inline atomic write for broker meta.ini updates (NTFS + POSIX safe)."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = _tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".tmp-",
        suffix=path.suffix,
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file_obj:
            file_obj.write(content)
            file_obj.flush()
            os.fsync(file_obj.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _handle_mods_meta_write(organizer, pump, payload):
    """Write meta.ini fields atomically and notify MO2 on the main thread."""

    name = payload.get("name")
    updates = payload.get("updates")
    if not isinstance(name, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "name: str"},
        }
    if not isinstance(updates, dict):
        return {
            "ok": False,
            "result": None,
            "error": {
                "code": ErrorCode.INVALID_PARAMS,
                "message": "updates: dict[section, dict[key, value]]",
            },
        }

    mod_list = organizer.modList()
    mod = mod_list.getMod(name)
    if mod is None:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MOD_NOT_FOUND, "message": name},
        }

    meta_path = Path(mod.absolutePath()) / "meta.ini"
    parser = _configparser.ConfigParser(interpolation=None)
    parser.optionxform = str
    if meta_path.exists():
        parser.read(meta_path, encoding="utf-8")

    for section, fields in updates.items():
        if not isinstance(fields, dict):
            continue
        section_name = str(section)
        if not parser.has_section(section_name):
            parser.add_section(section_name)
        for key, value in fields.items():
            parser.set(section_name, str(key), str(value))

    buffer = _StringIO()
    parser.write(buffer)
    try:
        _atomic_write_text_inline(meta_path, buffer.getvalue())
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INTERNAL_ERROR, "message": f"meta.ini write failed: {exc}"},
        }

    updated_sections = list(updates.keys())
    try:
        pump.invoke_blocking(lambda: organizer.modDataChanged(mod), timeout_s=5)
    except Exception as exc:
        return {
            "ok": True,
            "result": {
                "name": name,
                "updated_sections": updated_sections,
                "notification_skipped": str(exc),
            },
            "error": None,
        }

    return {
        "ok": True,
        "result": {"name": name, "updated_sections": updated_sections},
        "error": None,
    }


def _handle_plugins_list(organizer, payload):
    """Background-safe snapshot of plugins via IPluginList."""

    plugin_list = organizer.pluginList()
    plugins = []
    for name in plugin_list.pluginNames():
        state = plugin_list.state(name)
        state_int = int(state)
        plugins.append(
            {
                "name": name,
                "state": state_int,
                "enabled": bool(state_int & _ACTIVE_FLAG),
                "priority": plugin_list.priority(name),
                "load_order": plugin_list.loadOrder(name),
                "origin": plugin_list.origin(name),
                "is_master": bool(plugin_list.isMasterFlagged(name)),
                "is_light": bool(plugin_list.isLightFlagged(name)),
                "has_master_ext": bool(plugin_list.hasMasterExtension(name)),
                "has_light_ext": bool(plugin_list.hasLightExtension(name)),
            }
        )

    return {"ok": True, "result": {"plugins": plugins}, "error": None}


def _handle_plugins_set_state(organizer, pump, payload):
    """Set plugin active/inactive via main-thread setState + readback."""

    name = payload.get("name")
    state = payload.get("state")
    if not isinstance(name, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "name: str"},
        }
    if not isinstance(state, int):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "state: int"},
        }

    def _main():
        plugin_list = organizer.pluginList()
        if name not in plugin_list.pluginNames():
            return ("error", ErrorCode.PLUGIN_NOT_FOUND, name)
        plugin_list.setState(name, state)
        return (
            "ok",
            {
                "name": name,
                "requested_state": state,
                "actual_state": int(plugin_list.state(name)),
            },
        )

    try:
        outcome = pump.invoke_blocking(_main, timeout_s=10)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    if outcome[0] == "error":
        return {
            "ok": False,
            "result": None,
            "error": {"code": outcome[1], "message": outcome[2]},
        }
    return {"ok": True, "result": outcome[1], "error": None}


def _handle_plugins_set_priority(organizer, pump, payload):
    """Set plugin priority via main-thread setPriority + silent-noop readback."""

    name = payload.get("name")
    priority = payload.get("priority")
    if not isinstance(name, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "name: str"},
        }
    if not isinstance(priority, int):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "priority: int"},
        }

    def _main():
        plugin_list = organizer.pluginList()
        if name not in plugin_list.pluginNames():
            return ("error", ErrorCode.PLUGIN_NOT_FOUND, name)
        before = plugin_list.priority(name)
        plugin_list.setPriority(name, priority)
        after = plugin_list.priority(name)
        return (
            "ok",
            {
                "name": name,
                "requested_priority": priority,
                "actual_priority": after,
                "noop": after == before and before != priority,
            },
        )

    try:
        outcome = pump.invoke_blocking(_main, timeout_s=10)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    if outcome[0] == "error":
        return {
            "ok": False,
            "result": None,
            "error": {"code": outcome[1], "message": outcome[2]},
        }
    return {"ok": True, "result": outcome[1], "error": None}


def _handle_plugins_set_load_order(organizer, pump, payload):
    """Bulk reorder plugins via setLoadOrder + effective-order readback."""

    order = payload.get("load_order")
    if not isinstance(order, list) or not all(isinstance(name, str) for name in order):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "load_order: list[str]"},
        }

    def _main():
        plugin_list = organizer.pluginList()
        known = set(plugin_list.pluginNames())
        unknown = [name for name in order if name not in known]
        if unknown:
            return ("error", ErrorCode.PLUGIN_NOT_FOUND, f"unknown plugins in load_order: {unknown}")

        plugin_list.setLoadOrder(order)
        effective = sorted(plugin_list.pluginNames(), key=lambda name: plugin_list.priority(name))
        return (
            "ok",
            {
                "requested_explicit": list(order),
                "effective_order": effective,
                "implicitly_appended_count": len(effective) - len(order),
            },
        )

    try:
        outcome = pump.invoke_blocking(_main, timeout_s=15)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    if outcome[0] == "error":
        return {
            "ok": False,
            "result": None,
            "error": {"code": outcome[1], "message": outcome[2]},
        }
    return {"ok": True, "result": outcome[1], "error": None}


def _handle_profile_list(organizer, payload):
    """Background-safe: enumerate profile dirs containing modlist.txt."""

    base_path = Path(organizer.basePath())
    profiles_root = base_path / "profiles"
    profiles = []
    if profiles_root.exists():
        for child in sorted(profiles_root.iterdir(), key=lambda path: path.name):
            if not child.is_dir():
                continue
            if not (child / "modlist.txt").exists():
                continue
            profiles.append(
                {
                    "name": child.name,
                    "path": str(child),
                    "has_local_inis": (child / "settings.txt").exists(),
                }
            )
    return {"ok": True, "result": {"profiles": profiles}, "error": None}


def _handle_profile_active(organizer, payload):
    """Background-safe snapshot of current profile name + path."""

    return {
        "ok": True,
        "result": {"name": organizer.profileName(), "path": organizer.profilePath()},
        "error": None,
    }


def _handle_profile_initialize(organizer, pump, payload):
    """Initialize a profile directory with game-specific INI templates."""

    profile_dir = payload.get("profile_dir")
    settings_list = payload.get("settings", ["MODS", "CONFIGURATION"])
    if not isinstance(profile_dir, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "profile_dir: str"},
        }
    if not isinstance(settings_list, list) or not all(isinstance(setting, str) for setting in settings_list):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "settings: list[str]"},
        }

    def _main():
        try:
            from mobase import ProfileSetting
        except ImportError:
            return ("error", ErrorCode.INTERNAL_ERROR, "mobase.ProfileSetting unavailable")

        plugin_game = organizer.managedGame()
        if plugin_game is None:
            return ("error", ErrorCode.INTERNAL_ERROR, "no managed game plugin")

        flags = 0
        applied = []
        for setting in settings_list:
            attr = getattr(ProfileSetting, setting, None)
            if attr is None:
                return ("error", ErrorCode.INVALID_PARAMS, f"unknown ProfileSetting: {setting}")
            flags |= int(attr)
            applied.append(setting)

        try:
            from PyQt6.QtCore import QDir

            plugin_game.initializeProfile(QDir(profile_dir), flags)
        except ImportError:
            plugin_game.initializeProfile(profile_dir, flags)
        return ("ok", {"profile_dir": profile_dir, "settings_applied": applied})

    try:
        outcome = pump.invoke_blocking(_main, timeout_s=30)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    if outcome[0] == "error":
        return {
            "ok": False,
            "result": None,
            "error": {"code": outcome[1], "message": outcome[2]},
        }
    return {"ok": True, "result": outcome[1], "error": None}


def _handle_executables_list(organizer, payload):
    """Background-safe: list MO2 customExecutables from ModOrganizer.ini."""

    ini_path = Path(organizer.basePath()) / "ModOrganizer.ini"
    if not ini_path.exists():
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INTERNAL_ERROR, "message": f"ModOrganizer.ini not found at {ini_path}"},
        }

    import sys as _sys

    broker_dir = str(Path(__file__).parent)
    if broker_dir not in _sys.path:
        _sys.path.insert(0, broker_dir)
    try:
        from qt_ini import parse_custom_executables
    except ImportError as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INTERNAL_ERROR, "message": f"qt_ini import: {exc}"},
        }

    entries = parse_custom_executables(ini_path)
    return {
        "ok": True,
        "result": {"executables": entries, "count": len(entries)},
        "error": None,
    }


def _handle_installation_install_local_archive(organizer, pump, payload):
    """Install mod from local archive via IOrganizer.installMod.

    FOMOD-blind primitive: FOMOD wizard runs inside MO2 when archive contains
    info.xml. The MCP layer (S5a mo2_install) orchestrates FOMOD non-interactive
    via sidecar Pattern A; this is the raw mobase call.
    """

    archive_path = payload.get("archive_path")
    name_suggestion = payload.get("name_suggestion", "")
    if not isinstance(archive_path, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "archive_path: str"},
        }
    if not Path(archive_path).exists():
        return {
            "ok": False,
            "result": None,
            "error": {
                "code": ErrorCode.INVALID_PARAMS,
                "message": f"archive_path not found: {archive_path}",
            },
        }
    if not isinstance(name_suggestion, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "name_suggestion: str"},
        }

    def _on_main_thread():
        mod = organizer.installMod(archive_path, name_suggestion)
        if mod is None:
            return ("error", ErrorCode.INTERNAL_ERROR, "installMod returned None (canceled or failed)")
        return (
            "ok",
            {
                "name": mod.name(),
                "absolute_path": mod.absolutePath(),
                "installation_file": archive_path,
            },
        )

    try:
        outcome = pump.invoke_blocking(_on_main_thread, timeout_s=120)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    if outcome[0] == "error":
        return {
            "ok": False,
            "result": None,
            "error": {"code": outcome[1], "message": outcome[2]},
        }
    return {"ok": True, "result": outcome[1], "error": None}


def _handle_installation_create_mod_from_directory(organizer, pump, payload):
    """Create empty mod for Pattern A staging. Sister of mods.create in install namespace.

    Used by S5a mo2_install: sidecar pre-stages files in staging dir, then this
    handler creates the empty mod via IOrganizer.createMod. TS MCP layer moves
    staged content + writes meta.ini after this returns.
    """

    name = payload.get("name")
    if not isinstance(name, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "name: str"},
        }

    sanitized = _sanitize_dir_name(name)
    if not sanitized:
        return {
            "ok": False,
            "result": None,
            "error": {
                "code": ErrorCode.INVALID_PARAMS,
                "message": f"name '{name}' empty after sanitize",
            },
        }

    def _on_main_thread():
        mod_list = organizer.modList()
        if mod_list.getMod(sanitized) is not None:
            return ("error", ErrorCode.INVALID_PARAMS, f"name '{sanitized}' already exists")
        if GuessedString is None:
            return ("error", ErrorCode.INTERNAL_ERROR, "mobase.GuessedString unavailable")
        new_mod = organizer.createMod(GuessedString(sanitized))
        if new_mod is None:
            return ("error", ErrorCode.INTERNAL_ERROR, "createMod returned None")
        return (
            "ok",
            {
                "name": new_mod.name(),
                "absolute_path": new_mod.absolutePath(),
            },
        )

    try:
        outcome = pump.invoke_blocking(_on_main_thread, timeout_s=15)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    if outcome[0] == "error":
        return {
            "ok": False,
            "result": None,
            "error": {"code": outcome[1], "message": outcome[2]},
        }
    return {"ok": True, "result": outcome[1], "error": None}


def _handle_organizer_refresh(organizer, pump, payload):
    """Refresh MO2 internal state on the main thread."""

    save_changes = payload.get("save_changes", True)
    if not isinstance(save_changes, bool):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "save_changes: bool"},
        }

    def _main():
        organizer.refresh(save_changes)
        return {
            "refreshed": True,
            "save_changes": save_changes,
            "timestamp_ms": int(time.time() * 1000),
        }

    try:
        result = pump.invoke_blocking(_main, timeout_s=60)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    return {"ok": True, "result": result, "error": None}


def _handle_organizer_resolve_path(organizer, payload):
    """Background-safe: resolve a virtual path to a real on-disk path."""

    filename = payload.get("filename")
    if not isinstance(filename, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "filename: str"},
        }

    resolved = organizer.resolvePath(filename)
    return {
        "ok": True,
        "result": {"filename": filename, "resolved": resolved or None},
        "error": None,
    }


def _handle_organizer_get_file_origins(organizer, payload):
    """Background-safe: return mods providing a virtual file."""

    filename = payload.get("filename")
    if not isinstance(filename, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "filename: str"},
        }

    origins = list(organizer.getFileOrigins(filename) or [])
    return {
        "ok": True,
        "result": {"filename": filename, "origins": origins},
        "error": None,
    }


def _handle_organizer_find_files(organizer, payload):
    """Background-safe: find files matching glob patterns under a virtual path."""

    path = payload.get("path", "")
    patterns = payload.get("patterns", ["*"])
    if not isinstance(path, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "path: str"},
        }
    if not isinstance(patterns, list) or not all(isinstance(pattern, str) for pattern in patterns):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "patterns: list[str]"},
        }

    found = list(organizer.findFiles(path, patterns) or [])
    return {
        "ok": True,
        "result": {"path": path, "patterns": patterns, "files": found},
        "error": None,
    }


def _handle_organizer_virtual_file_tree(organizer, payload):
    """Background-safe: confirm virtual file tree liveness with a bounded response."""

    path = payload.get("path", "")
    max_depth = payload.get("max_depth", 3)
    if not isinstance(path, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "path: str"},
        }
    if not isinstance(max_depth, int):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "max_depth: int"},
        }

    try:
        organizer.virtualFileTree()
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INTERNAL_ERROR, "message": str(exc)},
        }

    return {
        "ok": True,
        "result": {
            "path": path,
            "max_depth": max_depth,
            "entries": [],
            "truncated": False,
            "note": "Use organizer.find_files for content; this method confirms VFS liveness",
        },
        "error": None,
    }


def _handle_organizer_startApplication(organizer, pump, payload):
    """Launch an executable through MO2 VFS via IOrganizer.startApplication."""

    name_or_path = payload.get("executable")
    args_list = payload.get("args", [])
    cwd = payload.get("cwd", "")
    profile = payload.get("profile", "")
    forced_overwrite = payload.get("forcedCustomOverwrite", "")
    ignore_overwrite = payload.get("ignoreCustomOverwrite", False)

    if not isinstance(name_or_path, str):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "executable: str"},
        }
    if not isinstance(args_list, list) or not all(isinstance(arg, str) for arg in args_list):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "args: list[str]"},
        }

    def _main():
        handle = organizer.startApplication(
            name_or_path,
            args_list,
            cwd,
            profile,
            forced_overwrite,
            ignore_overwrite,
        )
        if handle == 0:
            return (
                "error",
                ErrorCode.INTERNAL_ERROR,
                f"startApplication returned 0 (launch failed for '{name_or_path}')",
            )
        return ("ok", {"handle": int(handle), "executable": name_or_path})

    try:
        outcome = pump.invoke_blocking(_main, timeout_s=15)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    if outcome[0] == "error":
        return {
            "ok": False,
            "result": None,
            "error": {"code": outcome[1], "message": outcome[2]},
        }
    return {"ok": True, "result": outcome[1], "error": None}


def _handle_organizer_waitForApplication(organizer, pump, payload):
    """Wait for a launched application handle; refresh on completion by default."""

    handle = payload.get("handle")
    refresh = payload.get("refresh", True)
    if not isinstance(handle, int):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "handle: int"},
        }
    if not isinstance(refresh, bool):
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.INVALID_PARAMS, "message": "refresh: bool"},
        }

    def _main():
        success, exit_code = organizer.waitForApplication(handle, refresh)
        return {
            "handle": handle,
            "success": bool(success),
            "exit_code": int(exit_code) if exit_code is not None else None,
        }

    try:
        result = pump.invoke_blocking(_main, timeout_s=3600)
    except Exception as exc:
        return {
            "ok": False,
            "result": None,
            "error": {"code": ErrorCode.MAIN_THREAD_UNAVAILABLE, "message": str(exc)},
        }

    return {"ok": True, "result": result, "error": None}


def utc_now_timestamp() -> str:
    """Return a stable UTC timestamp string for registry entries."""

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def get_blocker_events_path(runtime_root: str | Path | None = None) -> Path:
    """Return the runtime blocker-event log path."""

    root = Path(runtime_root) if runtime_root is not None else get_runtime_root()
    return root / BLOCKER_EVENTS_FILE


def match_blocker_dialog(title, text, buttons):
    """Return the whitelisted blocker dialog descriptor or None."""

    normalized_title = str(title or "")
    normalized_text = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized_buttons = tuple(str(button) for button in (buttons or []))

    for candidate in KNOWN_BLOCKER_DIALOGS:
        if normalized_title != candidate["title"]:
            continue

        if normalized_buttons != tuple(candidate["buttons"]):
            continue

        if not normalized_text.startswith(str(candidate["textPrefix"])):
            continue

        return {
            "type": candidate["type"],
            "title": normalized_title,
            "text": normalized_text,
            "buttons": list(normalized_buttons),
        }

    return None


def append_blocker_event(runtime_root, event):
    """Append one blocker event record to the runtime JSONL log."""

    blocker_events_path = get_blocker_events_path(runtime_root)
    blocker_events_path.parent.mkdir(parents=True, exist_ok=True)
    with blocker_events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(dict(event), ensure_ascii=False) + "\n")

    return blocker_events_path


def create_launch_registry() -> dict[str, dict[str, dict[str, object]]]:
    """Create the in-memory launch registry for tracked live processes."""

    return {
        LAUNCH_REGISTRY_ENTRIES_FIELD: {},
    }


def create_launch_registry_entry(
    launch_id: str,
    request: dict[str, object],
    payload: dict[str, object] | None = None,
) -> dict[str, object]:
    """Create the minimal launch registry entry shape without live process data."""

    payload = payload or {}
    timestamp = utc_now_timestamp()
    return {
        "launch_id": launch_id,
        "session_id": request.get("session_id"),
        "target_path": payload.get("target_path"),
        "args": list(payload.get("args") or []),
        "cwd": payload.get("cwd"),
        "env": dict(payload.get("env") or {}),
        "pid": None,
        "process_handle": None,
        "status": LAUNCH_REGISTRY_STATUS_PENDING,
        "started_at": None,
        "updated_at": timestamp,
        "exit_code": None,
        "artifacts": {
            "state_file": None,
            "backend": None,
        },
    }


def normalize_launch_start_payload(request: dict[str, object]) -> dict[str, object]:
    """Accept either direct launch payloads or the broker transport wrapper."""

    payload = dict(request.get("payload") or {})
    if isinstance(payload.get("transport"), dict):
        payload = dict(payload["transport"])

    target_path = str(payload.get("target_path") or "").strip()
    if not target_path:
        raise ValueError("launch.start requires payload target_path")

    payload["target_path"] = target_path
    payload["args"] = [str(arg) for arg in list(payload.get("args") or [])]
    payload["cwd"] = payload.get("cwd")
    payload["env"] = dict(payload.get("env") or {})
    return payload


def create_launch_id() -> str:
    """Return a stable launch identifier."""

    return f"launch-{uuid.uuid4().hex}"


def build_launch_result(entry: dict[str, object]) -> dict[str, object]:
    """Project an in-memory launch entry into the transport response shape."""

    result = {
        "launch_id": entry.get("launch_id"),
        "pid": entry.get("pid"),
        "status": entry.get("status"),
    }

    if entry.get("started_at") is not None:
        result["started_at"] = entry.get("started_at")

    if entry.get("exit_code") is not None:
        result["exit_code"] = entry.get("exit_code")

    if entry.get("artifacts") is not None:
        result["artifacts"] = entry.get("artifacts")

    return result


def mark_launch_entry_updated(entry: dict[str, object]) -> dict[str, object]:
    """Stamp the launch entry update time and return the same entry."""

    entry["updated_at"] = utc_now_timestamp()
    return entry


def mark_launch_entry_completed(entry: dict[str, object], exit_code: int) -> dict[str, object]:
    """Transition a running launch entry into a completed state."""

    entry["exit_code"] = int(exit_code)
    entry["process_handle"] = None
    entry["status"] = LAUNCH_REGISTRY_STATUS_COMPLETED
    return mark_launch_entry_updated(entry)


def mark_launch_entry_stopped(entry: dict[str, object], exit_code: int | None = None) -> dict[str, object]:
    """Transition a running launch entry into a stopped state."""

    if exit_code is not None:
        entry["exit_code"] = int(exit_code)

    entry["process_handle"] = None
    entry["status"] = LAUNCH_REGISTRY_STATUS_STOPPED
    return mark_launch_entry_updated(entry)


def open_process_handle_for_pid(pid: int, desired_access: int):
    """Open a live process handle for the requested PID or return None."""

    handle = KERNEL32.OpenProcess(desired_access, False, pid)
    if not handle:
        return None

    return handle


def get_exit_code_from_process_handle(process_handle) -> int | None:
    """Return the exit code for a process handle, or None if it is still running."""

    exit_code = ctypes.c_uint32()
    success = KERNEL32.GetExitCodeProcess(process_handle, ctypes.byref(exit_code))
    if not success:
        raise_last_windows_error("Failed to query process exit code")

    if exit_code.value == STILL_ACTIVE:
        return None

    return int(exit_code.value)


def get_launch_exit_code(entry: dict[str, object]) -> int | None:
    """Return the exit code for a tracked launch when it has already exited."""

    process_handle = entry.get("process_handle")
    if process_handle is not None:
        exit_code = process_handle.poll()
        if exit_code is None:
            return None

        return int(exit_code)

    pid = entry.get("pid")
    if pid is None:
        return None

    handle = open_process_handle_for_pid(int(pid), PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE)
    if handle is None:
        return None

    try:
        return get_exit_code_from_process_handle(handle)
    finally:
        KERNEL32.CloseHandle(handle)


def refresh_launch_entry(entry: dict[str, object]) -> dict[str, object]:
    """Refresh a launch entry in place using the current process state."""

    if entry.get("status") != LAUNCH_REGISTRY_STATUS_RUNNING:
        return entry

    exit_code = get_launch_exit_code(entry)
    if exit_code is None:
        return entry

    return mark_launch_entry_completed(entry, exit_code)


def refresh_launch_entry_threadsafe(entry: dict[str, object], entry_condition: threading.Condition) -> dict[str, object]:
    """Refresh a launch entry while holding the per-launch coordination lock."""

    with entry_condition:
        return refresh_launch_entry(entry)


def wait_for_pid_exit(pid: int) -> int | None:
    """Wait for a process PID to exit and return its exit code when observable."""

    handle = open_process_handle_for_pid(int(pid), PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE)
    if handle is None:
        return None

    try:
        wait_result = KERNEL32.WaitForSingleObject(handle, INFINITE)
        if wait_result not in (WAIT_OBJECT_0, WAIT_TIMEOUT):
            raise_last_windows_error("Failed while waiting for process exit")

        return get_exit_code_from_process_handle(handle)
    finally:
        KERNEL32.CloseHandle(handle)


def wait_for_launch_entry(entry: dict[str, object]) -> dict[str, object]:
    """Block until a tracked launch exits, then update the registry entry."""

    if entry.get("status") != LAUNCH_REGISTRY_STATUS_RUNNING:
        return entry

    process_handle = entry.get("process_handle")
    if process_handle is not None:
        return mark_launch_entry_completed(entry, int(process_handle.wait()))

    pid = entry.get("pid")
    if pid is None:
        return entry

    exit_code = wait_for_pid_exit(int(pid))
    if exit_code is None:
        return entry

    return mark_launch_entry_completed(entry, exit_code)


def wait_for_launch_entry_threadsafe(entry: dict[str, object], entry_condition: threading.Condition) -> dict[str, object]:
    """Wait for a tracked launch without holding the per-launch lock while blocked."""

    with entry_condition:
        entry = refresh_launch_entry(entry)
        if entry.get("status") != LAUNCH_REGISTRY_STATUS_RUNNING:
            return entry

        process_handle = entry.get("process_handle")
        pid = entry.get("pid")

    if process_handle is not None:
        exit_code = int(process_handle.wait())
    elif pid is None:
        exit_code = None
    else:
        exit_code = wait_for_pid_exit(int(pid))

    with entry_condition:
        while entry.get("_stop_requested") and entry.get("status") == LAUNCH_REGISTRY_STATUS_RUNNING:
            entry_condition.wait(timeout=5)

        if entry.get("status") != LAUNCH_REGISTRY_STATUS_RUNNING:
            return entry

        if exit_code is None:
            return refresh_launch_entry(entry)

        return mark_launch_entry_completed(entry, exit_code)


def stop_launch_entry(entry: dict[str, object]) -> dict[str, object]:
    """Terminate a tracked process when still running and mark it stopped."""

    entry = refresh_launch_entry(entry)
    if entry.get("status") != LAUNCH_REGISTRY_STATUS_RUNNING:
        return entry

    process_handle = entry.get("process_handle")
    if process_handle is not None:
        process_handle.terminate()
        try:
            exit_code = int(process_handle.wait(timeout=5))
        except subprocess.TimeoutExpired:
            process_handle.kill()
            exit_code = int(process_handle.wait(timeout=5))

        return mark_launch_entry_stopped(entry, exit_code)

    pid = entry.get("pid")
    if pid is None:
        return mark_launch_entry_stopped(entry)

    handle = open_process_handle_for_pid(
        int(pid),
        PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
    )
    if handle is None:
        return mark_launch_entry_stopped(entry)

    try:
        success = KERNEL32.TerminateProcess(handle, 1)
        if not success:
            raise_last_windows_error("Failed to stop tracked launch")

        KERNEL32.WaitForSingleObject(handle, INFINITE)
        exit_code = get_exit_code_from_process_handle(handle)
        return mark_launch_entry_stopped(entry, exit_code)
    finally:
        KERNEL32.CloseHandle(handle)


def stop_launch_entry_threadsafe(entry: dict[str, object], entry_condition: threading.Condition) -> dict[str, object]:
    """Stop a tracked launch without holding the per-launch lock while blocked."""

    with entry_condition:
        entry = refresh_launch_entry(entry)
        if entry.get("status") != LAUNCH_REGISTRY_STATUS_RUNNING:
            return entry

        entry["_stop_requested"] = True
        process_handle = entry.get("process_handle")
        pid = entry.get("pid")

    if process_handle is not None:
        process_handle.terminate()
        try:
            exit_code = int(process_handle.wait(timeout=5))
        except subprocess.TimeoutExpired:
            process_handle.kill()
            exit_code = int(process_handle.wait(timeout=5))
    elif pid is None:
        exit_code = None
    else:
        handle = open_process_handle_for_pid(
            int(pid),
            PROCESS_TERMINATE | PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE,
        )
        if handle is None:
            exit_code = None
        else:
            try:
                success = KERNEL32.TerminateProcess(handle, 1)
                if not success:
                    raise_last_windows_error("Failed to stop tracked launch")

                KERNEL32.WaitForSingleObject(handle, INFINITE)
                exit_code = get_exit_code_from_process_handle(handle)
            finally:
                KERNEL32.CloseHandle(handle)

    with entry_condition:
        try:
            if entry.get("status") != LAUNCH_REGISTRY_STATUS_RUNNING:
                return entry

            return mark_launch_entry_stopped(entry, exit_code)
        finally:
            entry["_stop_requested"] = False
            entry_condition.notify_all()


def get_launch_entry(
    launch_registry: dict[str, dict[str, dict[str, object]]],
    launch_id: str,
) -> dict[str, object]:
    """Return a tracked launch entry or raise a validation error."""

    if not launch_id:
        raise ValueError("launch_id is required")

    launches = launch_registry[LAUNCH_REGISTRY_ENTRIES_FIELD]
    if launch_id not in launches:
        raise ValueError(f"Unknown launch_id: {launch_id}")

    return launches[launch_id]


def prune_terminal_launches(
    launch_registry: dict[str, dict[str, dict[str, object]]],
    launch_entry_locks: dict[str, threading.Condition],
    retention_limit: int = TERMINAL_LAUNCH_RETENTION_LIMIT,
) -> None:
    """Retain only the newest bounded set of terminal launch entries and locks."""

    if retention_limit < 0:
        return

    launches = launch_registry[LAUNCH_REGISTRY_ENTRIES_FIELD]
    terminal_launch_ids = [
        launch_id
        for launch_id, entry in launches.items()
        if entry.get("status") in (LAUNCH_REGISTRY_STATUS_COMPLETED, LAUNCH_REGISTRY_STATUS_STOPPED)
    ]
    excess_count = len(terminal_launch_ids) - retention_limit
    if excess_count <= 0:
        return

    for launch_id in terminal_launch_ids[:excess_count]:
        launches.pop(launch_id, None)
        launch_entry_locks.pop(launch_id, None)


def start_subprocess_launch(payload: dict[str, object]) -> subprocess.Popen:
    """Start a subprocess-backed launch for harness and fallback use."""

    target_path = str(payload["target_path"])
    args = [target_path, *payload.get("args", [])]
    cwd = payload.get("cwd") or None
    env = os.environ.copy()
    env.update({str(key): str(value) for key, value in payload.get("env", {}).items()})
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        args,
        cwd=cwd,
        env=env,
        creationflags=creation_flags,
    )


def start_organizer_launch(organizer, payload: dict[str, object]) -> int | None:
    """Prefer MO2's organizer launch API when it is available."""

    if organizer is None or not hasattr(organizer, "startApplication"):
        return None

    start_application = getattr(organizer, "startApplication")
    target_path = str(payload["target_path"])
    args = list(payload.get("args", []))
    cwd = str(payload.get("cwd") or "")

    for call_args in (
        (target_path, args, cwd, ""),
        (target_path, args, cwd),
        (target_path, args),
    ):
        try:
            launch_pid = start_application(*call_args)
        except TypeError:
            continue

        if launch_pid is None:
            raise RuntimeError("Organizer launch failed to return a process id")

        return int(launch_pid)

    return None


def handle_launch_start(
    request: dict[str, object],
    launch_registry: dict[str, dict[str, dict[str, object]]],
    organizer=None,
    main_thread_pump: MainThreadCallPump | None = None,
) -> dict[str, object]:
    """Start a tracked process and return its launch metadata."""

    payload = normalize_launch_start_payload(request)
    launch_id = create_launch_id()
    entry = create_launch_registry_entry(launch_id, request, payload)
    entry["started_at"] = utc_now_timestamp()
    entry["status"] = LAUNCH_REGISTRY_STATUS_RUNNING
    organizer_pid = None
    if organizer is not None and hasattr(organizer, "startApplication"):
        if main_thread_pump is None:
            raise NotImplementedError("Organizer-backed launch.start requires a main-thread pump")

        organizer_pid = main_thread_pump.invoke(lambda: start_organizer_launch(organizer, payload))

    if organizer_pid is not None:
        entry["pid"] = organizer_pid
        entry["artifacts"]["backend"] = "organizer"
    else:
        process_handle = start_subprocess_launch(payload)
        entry["process_handle"] = process_handle
        entry["pid"] = int(process_handle.pid)
        entry["artifacts"]["backend"] = "subprocess"

    mark_launch_entry_updated(entry)
    launch_registry[LAUNCH_REGISTRY_ENTRIES_FIELD][launch_id] = entry
    return build_launch_result(entry)


def handle_launch_status(
    request: dict[str, object],
    launch_registry: dict[str, dict[str, dict[str, object]]],
    entry_lock: threading.Condition | None = None,
) -> dict[str, object]:
    """Return the current state for a tracked launch."""

    launch_id = str((request.get("payload") or {}).get("launch_id") or "").strip()
    entry = get_launch_entry(launch_registry, launch_id)
    if entry_lock is not None:
        entry = refresh_launch_entry_threadsafe(entry, entry_lock)
    else:
        entry = refresh_launch_entry(entry)
    return build_launch_result(entry)


def handle_launch_wait(
    request: dict[str, object],
    launch_registry: dict[str, dict[str, dict[str, object]]],
    entry_lock: threading.Condition | None = None,
) -> dict[str, object]:
    """Wait for a tracked launch to finish and return its terminal state."""

    launch_id = str((request.get("payload") or {}).get("launch_id") or "").strip()
    entry = get_launch_entry(launch_registry, launch_id)
    if entry_lock is not None:
        entry = wait_for_launch_entry_threadsafe(entry, entry_lock)
    else:
        entry = wait_for_launch_entry(entry)
    return build_launch_result(entry)


def handle_launch_stop(
    request: dict[str, object],
    launch_registry: dict[str, dict[str, dict[str, object]]],
    entry_lock: threading.Condition | None = None,
) -> dict[str, object]:
    """Stop a tracked launch and return its updated state."""

    launch_id = str((request.get("payload") or {}).get("launch_id") or "").strip()
    entry = get_launch_entry(launch_registry, launch_id)
    if entry_lock is not None:
        entry = stop_launch_entry_threadsafe(entry, entry_lock)
    else:
        entry = stop_launch_entry(entry)
    return build_launch_result(entry)


def build_command_handlers(
    launch_registry: dict[str, dict[str, dict[str, object]]] | None = None,
    organizer=None,
    main_thread_pump: MainThreadCallPump | None = None,
):
    """Return the command handler registry for system and launch methods."""

    launch_registry = launch_registry if launch_registry is not None else create_launch_registry()
    _set_main_thread_pump(main_thread_pump)
    launch_registry_lock = threading.Lock()
    launch_entry_locks: dict[str, threading.Condition] = {}
    handlers = {
        SYSTEM_PING_METHOD: handle_system_ping,
    }

    def get_launch_entry_and_lock(launch_id: str) -> tuple[dict[str, object], threading.Condition]:
        with launch_registry_lock:
            entry = get_launch_entry(launch_registry, launch_id)
            return entry, launch_entry_locks[launch_id]

    def handle_launch_request(request: dict[str, object], method_name: str) -> dict[str, object]:
        if method_name == LAUNCH_START_METHOD:
            with launch_registry_lock:
                result = handle_launch_start(
                    request,
                    launch_registry,
                    organizer=organizer,
                    main_thread_pump=main_thread_pump,
                )
                launch_entry_locks[result["launch_id"]] = threading.Condition()
                prune_terminal_launches(launch_registry, launch_entry_locks)
                return result

        launch_id = str((request.get("payload") or {}).get("launch_id") or "").strip()
        _entry, entry_lock = get_launch_entry_and_lock(launch_id)
        if method_name == LAUNCH_STATUS_METHOD:
            result = handle_launch_status(request, launch_registry, entry_lock=entry_lock)
        elif method_name == LAUNCH_WAIT_METHOD:
            result = handle_launch_wait(request, launch_registry, entry_lock=entry_lock)
        elif method_name == LAUNCH_STOP_METHOD:
            result = handle_launch_stop(request, launch_registry, entry_lock=entry_lock)
        else:
            raise ValueError(f"Unsupported launch method: {method_name}")

        with launch_registry_lock:
            prune_terminal_launches(launch_registry, launch_entry_locks)
        return result

    for method_name in LAUNCH_METHODS:
        handlers[method_name] = lambda request, method_name=method_name: handle_launch_request(request, method_name)

    def handle_system_capabilities(_request: dict[str, object]) -> dict[str, object]:
        """Return the currently registered command surface."""

        return {
            "commands": sorted(handlers.keys()),
        }

    handlers[SYSTEM_CAPABILITIES_METHOD] = handle_system_capabilities
    handlers[SYSTEM_SHUTDOWN_METHOD] = lambda request: _handle_system_shutdown(
        organizer,
        request.get("payload", {}),
    )
    handlers[MODS_LIST_METHOD] = lambda request: _handle_mods_list(
        organizer,
        request.get("payload", {}),
    )
    handlers[MODS_SET_ACTIVE_METHOD] = lambda request: _handle_mods_set_active(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[MODS_SET_PRIORITY_METHOD] = lambda request: _handle_mods_set_priority(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[MODS_RENAME_METHOD] = lambda request: _handle_mods_rename(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[MODS_REMOVE_METHOD] = lambda request: _handle_mods_remove(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[MODS_CREATE_METHOD] = lambda request: _handle_mods_create(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[MODS_META_READ_METHOD] = lambda request: _handle_mods_meta_read(
        organizer,
        request.get("payload", {}),
    )
    handlers[MODS_META_WRITE_METHOD] = lambda request: _handle_mods_meta_write(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[PLUGINS_LIST_METHOD] = lambda request: _handle_plugins_list(
        organizer,
        request.get("payload", {}),
    )
    handlers[PLUGINS_SET_STATE_METHOD] = lambda request: _handle_plugins_set_state(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[PLUGINS_SET_PRIORITY_METHOD] = lambda request: _handle_plugins_set_priority(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[PLUGINS_SET_LOAD_ORDER_METHOD] = lambda request: _handle_plugins_set_load_order(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[PROFILE_LIST_METHOD] = lambda request: _handle_profile_list(
        organizer,
        request.get("payload", {}),
    )
    handlers[PROFILE_ACTIVE_METHOD] = lambda request: _handle_profile_active(
        organizer,
        request.get("payload", {}),
    )
    handlers[PROFILE_INITIALIZE_METHOD] = lambda request: _handle_profile_initialize(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[EXECUTABLES_LIST_METHOD] = lambda request: _handle_executables_list(
        organizer,
        request.get("payload", {}),
    )
    handlers[INSTALLATION_INSTALL_LOCAL_ARCHIVE_METHOD] = lambda request: _handle_installation_install_local_archive(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[INSTALLATION_CREATE_MOD_FROM_DIRECTORY_METHOD] = lambda request: _handle_installation_create_mod_from_directory(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[ORGANIZER_REFRESH_METHOD] = lambda request: _handle_organizer_refresh(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[ORGANIZER_RESOLVE_PATH_METHOD] = lambda request: _handle_organizer_resolve_path(
        organizer,
        request.get("payload", {}),
    )
    handlers[ORGANIZER_GET_FILE_ORIGINS_METHOD] = lambda request: _handle_organizer_get_file_origins(
        organizer,
        request.get("payload", {}),
    )
    handlers[ORGANIZER_FIND_FILES_METHOD] = lambda request: _handle_organizer_find_files(
        organizer,
        request.get("payload", {}),
    )
    handlers[ORGANIZER_VIRTUAL_FILE_TREE_METHOD] = lambda request: _handle_organizer_virtual_file_tree(
        organizer,
        request.get("payload", {}),
    )
    handlers[ORGANIZER_START_APPLICATION_METHOD] = lambda request: _handle_organizer_startApplication(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    handlers[ORGANIZER_WAIT_FOR_APPLICATION_METHOD] = lambda request: _handle_organizer_waitForApplication(
        organizer,
        main_thread_pump,
        request.get("payload", {}),
    )
    return handlers


def dispatch_transport_request(request: dict[str, object], handlers) -> dict[str, object]:
    """Route a single request through the local handler registry."""

    method = request.get("method") or request.get("command")
    if method is not None and request.get("method") != method:
        request = dict(request)
        request["method"] = method

    handler = handlers.get(method)
    if handler is None:
        return build_transport_response(
            request,
            ok=False,
            error={
                "code": ErrorCode.METHOD_NOT_FOUND,
                "message": f"Unsupported method: {method}",
            },
        )

    try:
        result = handler(request)
        if is_broker_handler_response(result):
            return build_transport_response(
                request,
                ok=bool(result["ok"]),
                result=result.get("result"),
                error=result.get("error"),
            )

        return build_transport_response(request, ok=True, result=result, error=None)
    except ValueError as exc:
        return build_transport_response(
            request,
            ok=False,
            error={
                "code": ErrorCode.INVALID_PARAMS,
                "message": str(exc),
            },
        )
    except OSError as exc:
        return build_transport_response(
            request,
            ok=False,
            error={
                "code": ErrorCode.TRANSPORT_ERROR,
                "message": str(exc),
            },
        )
    except NotImplementedError as exc:
        return build_transport_response(
            request,
            ok=False,
            error={
                "code": ErrorCode.NOT_IMPLEMENTED,
                "message": str(exc),
            },
        )
    except Exception as exc:  # pragma: no cover - fail closed for unexpected live errors.
        return build_transport_response(
            request,
            ok=False,
            error={
                "code": ErrorCode.INTERNAL_ERROR,
                "message": str(exc),
            },
        )


def bootstrap_named_pipe_server(runtime_root: str | Path, handlers, pipe_name: str | None = None):
    """Start a real background named-pipe server and return transport metadata."""

    resolved_pipe_name = get_runtime_pipe_name() if pipe_name is None else str(pipe_name)
    stop_event = threading.Event()
    server_thread = threading.Thread(
        target=serve_named_pipe_requests,
        args=(resolved_pipe_name, handlers, stop_event),
        name=f"{PLUGIN_NAME}-named-pipe-server",
        daemon=True,
    )
    server_thread.start()

    _ACTIVE_NAMED_PIPE_TRANSPORTS.append(
        {
            "endpoint": resolved_pipe_name,
            "pipePath": get_named_pipe_path(resolved_pipe_name),
            "stopEvent": stop_event,
            "thread": server_thread,
        }
    )

    return {
        "transport": RUNTIME_TRANSPORT,
        RUNTIME_ENDPOINT_FIELD: resolved_pipe_name,
        "pipePath": get_named_pipe_path(resolved_pipe_name),
        "runtimeRoot": str(Path(runtime_root)),
        "started": True,
    }


def start_transport(
    runtime_root: str | Path | None = None,
    organizer=None,
    main_thread_pump: MainThreadCallPump | None = None,
):
    """Start the live named-pipe transport after bootstrap publication."""

    resolved_runtime_root = Path(runtime_root) if runtime_root is not None else get_runtime_root()
    handlers = build_command_handlers(organizer=organizer, main_thread_pump=main_thread_pump)
    return bootstrap_named_pipe_server(resolved_runtime_root, handlers, pipe_name=get_runtime_pipe_name())


def get_runtime_root(module_path: str | Path | None = None) -> Path:
    """Return the deployed bootstrap runtime directory."""

    module_file = Path(module_path) if module_path is not None else Path(__file__)
    return (
        module_file.resolve().parent
        / PLUGIN_NAME
        / BOOTSTRAP_DIRECTORY_NAME
        / RUNTIME_DIRECTORY_NAME
    )


def write_runtime_json(runtime_file: Path, document: dict[str, object]) -> None:
    """Atomically replace a runtime JSON document to avoid partial reads."""

    temp_file = runtime_file.with_suffix(runtime_file.suffix + ".tmp")
    temp_file.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    os.replace(temp_file, runtime_file)


def publish_runtime_bootstrap(runtime_root: str | Path | None = None) -> Path:
    """Create the minimal live-bootstrap runtime files under the support directory."""

    root = Path(runtime_root) if runtime_root is not None else get_runtime_root()
    root.mkdir(parents=True, exist_ok=True)
    methods = sorted(build_command_handlers().keys())

    runtime_documents = {
        RUNTIME_STATUS_FILE: {
            "schemaVersion": RUNTIME_SCHEMA_VERSION,
            "state": RUNTIME_READY_STATE,
            "mo2Pid": os.getpid(),
        },
        RUNTIME_CAPABILITIES_FILE: {
            "schemaVersion": RUNTIME_SCHEMA_VERSION,
            "methods": methods,
        },
        RUNTIME_ENDPOINT_FILE: {
            "schemaVersion": RUNTIME_SCHEMA_VERSION,
            "transport": RUNTIME_TRANSPORT,
            RUNTIME_ENDPOINT_FIELD: get_runtime_pipe_name(),
        },
    }

    for file_name, document in runtime_documents.items():
        write_runtime_json(root / file_name, document)

    return root


class Mo2AgentControlPlugin(mobase.IPluginTool):
    """Minimal MO2 plugin that publishes discovery/liveness bootstrap evidence."""

    def __init__(self) -> None:
        super().__init__()
        self._organizer = None
        self._main_thread_pump = None
        self._main_thread_timer = None
        self._blocker_watcher_timer = None
        self._transport = None

    def init(self, organizer) -> bool:
        self._organizer = organizer
        self._main_thread_pump = MainThreadCallPump()
        self._main_thread_timer = install_main_thread_pump_timer(self._main_thread_pump)
        runtime_root = publish_runtime_bootstrap()
        self._blocker_watcher_timer = install_blocker_watcher_timer(runtime_root)
        self._transport = start_transport(
            runtime_root,
            organizer=organizer,
            main_thread_pump=self._main_thread_pump,
        )
        return True

    def name(self):
        return PLUGIN_NAME

    def author(self):
        return "Vault-Tec Automated Research Terminal"

    def description(self):
        return "Publishes file-bootstrap discovery/liveness evidence, not the command transport."

    def version(self):
        return mobase.VersionInfo(0, 1, 0, 0)

    def settings(self):
        return []

    def displayName(self):
        return PLUGIN_NAME

    def tooltip(self):
        return self.description()


def createPlugin() -> Mo2AgentControlPlugin:
    return Mo2AgentControlPlugin()

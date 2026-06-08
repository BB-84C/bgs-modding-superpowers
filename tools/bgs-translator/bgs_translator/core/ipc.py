"""Named-pipe and Unix-socket IPC for CLI-to-GUI prompt preview."""

from __future__ import annotations

import importlib
import json
import os
import socket
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

PreviewCallback = Callable[[str, str, list[dict[str, object]]], dict[str, Any]]


class IPCServer:
    """Listen for preview requests from CLI processes.

    Protocol is JSON line-delimited. Each connection carries one request and
    receives one response.
    """

    def __init__(self, on_preview_request: PreviewCallback, addr: str | None = None) -> None:
        self._on_preview = on_preview_request
        self._addr = addr or self._compute_addr()
        self._stop_event = threading.Event()
        self._ready_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None
        self._actual_addr = self._addr
        self._pending: dict[str, tuple[threading.Event, dict[str, Any]]] = {}
        self._pending_lock = threading.Lock()

    @property
    def address(self) -> str:
        """Return the concrete server address after ``start``."""

        return self._actual_addr

    @property
    def is_running(self) -> bool:
        """Return whether the accept thread is alive."""

        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """Start the background accept loop."""

        if self.is_running:
            return
        self._stop_event.clear()
        self._ready_event.clear()
        self._thread = threading.Thread(target=self._serve_loop, name="bgs-translator-ipc", daemon=True)
        self._thread.start()
        self._ready_event.wait(timeout=2.0)

    def stop(self) -> None:
        """Stop the accept loop and unblock any waiting socket call."""

        self._stop_event.set()
        self._poke_listener()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        self._thread = None
        sock = self._socket
        self._socket = None
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        if os.name != "nt" and not self._addr.startswith("tcp://"):
            try:
                Path(self._addr).unlink()
            except FileNotFoundError:
                pass

    def respond(
        self,
        batch_id: str,
        op: str,
        prompt: str | None = None,
        *,
        approve_all: bool = False,
        discard: bool = False,
    ) -> None:
        """Release a pending GUI-mediated preview request."""

        response: dict[str, Any]
        if discard or op == "discarded":
            response = {"op": "discarded"}
        elif approve_all or op == "approve_all":
            response = {"op": "approve_all", "prompt": prompt or ""}
        else:
            response = {"op": op, "prompt": prompt or ""}
        with self._pending_lock:
            pending = self._pending.get(batch_id)
            if pending is None:
                return
            event, bucket = pending
            bucket.clear()
            bucket.update(response)
            event.set()

    def _compute_addr(self) -> str:
        if os.name == "nt":
            user = os.environ.get("USERNAME", "user")
            return rf"\\.\pipe\bgs-translator-gui-{user}"
        return str(Path.home() / ".bgs-modding-superpowers" / "translator" / "bgs-translator-gui.sock")

    def _serve_loop(self) -> None:
        if self._addr.startswith("tcp://"):
            self._serve_socket(self._make_tcp_socket())
            return
        if os.name == "nt":
            self._serve_windows_pipe()
            return
        self._serve_socket(self._make_unix_socket())

    def _make_tcp_socket(self) -> socket.socket:
        host_port = self._addr.removeprefix("tcp://")
        host, port_text = host_port.rsplit(":", 1)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, int(port_text)))
        host_actual, port_actual = sock.getsockname()
        self._actual_addr = f"tcp://{host_actual}:{port_actual}"
        self._ready_event.set()
        return sock

    def _make_unix_socket(self) -> socket.socket:
        path = Path(self._addr)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        unix_family = socket.AF_UNIX  # type: ignore[attr-defined]
        sock = socket.socket(unix_family, socket.SOCK_STREAM)
        sock.bind(str(path))
        self._actual_addr = str(path)
        self._ready_event.set()
        return sock

    def _serve_socket(self, sock: socket.socket) -> None:
        self._socket = sock
        sock.listen()
        sock.settimeout(0.2)
        try:
            while not self._stop_event.is_set():
                try:
                    conn, _addr = sock.accept()
                except TimeoutError:
                    continue
                except OSError:
                    if self._stop_event.is_set():
                        break
                    continue
                with conn:
                    self._handle_connection(conn)
        finally:
            try:
                sock.close()
            except OSError:
                pass

    def _serve_windows_pipe(self) -> None:
        try:
            win32file = importlib.import_module("win32file")
            win32pipe = importlib.import_module("win32pipe")
        except ImportError:
            self._ready_event.set()
            return

        self._ready_event.set()
        while not self._stop_event.is_set():
            pipe = win32pipe.CreateNamedPipe(
                self._addr,
                win32pipe.PIPE_ACCESS_DUPLEX,
                win32pipe.PIPE_TYPE_BYTE | win32pipe.PIPE_READMODE_BYTE | win32pipe.PIPE_WAIT,
                1,
                65536,
                65536,
                1000,
                None,
            )
            try:
                win32pipe.ConnectNamedPipe(pipe, None)
                request = _read_pipe_json_line(pipe)
                response = self._dispatch_request(request)
                win32file.WriteFile(pipe, (json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))
            except Exception:
                if self._stop_event.is_set():
                    break
            finally:
                try:
                    win32pipe.DisconnectNamedPipe(pipe)
                except Exception:
                    pass
                win32file.CloseHandle(pipe)

    def _handle_connection(self, conn: socket.socket) -> None:
        try:
            request = _read_socket_json_line(conn)
            response = self._dispatch_request(request)
        except Exception as exc:
            response = {"op": "error", "message": str(exc)}
        conn.sendall((json.dumps(response, ensure_ascii=False) + "\n").encode("utf-8"))

    def _dispatch_request(self, request: dict[str, Any]) -> dict[str, Any]:
        if request.get("op") != "preview":
            return {"op": "error", "message": "unsupported op"}
        batch_id = str(request.get("batch_id", ""))
        prompt = str(request.get("prompt", ""))
        raw_items = request.get("items", [])
        items = [item for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []
        return self._on_preview(batch_id, prompt, items)

    def _poke_listener(self) -> None:
        try:
            if self._actual_addr.startswith("tcp://"):
                host_port = self._actual_addr.removeprefix("tcp://")
                host, port_text = host_port.rsplit(":", 1)
                with socket.create_connection((host, int(port_text)), timeout=0.2):
                    pass
            elif os.name != "nt":
                unix_family = socket.AF_UNIX  # type: ignore[attr-defined]
                with socket.socket(unix_family, socket.SOCK_STREAM) as sock:
                    sock.settimeout(0.2)
                    sock.connect(self._actual_addr)
        except OSError:
            pass


def _read_socket_json_line(conn: socket.socket) -> dict[str, Any]:
    chunks: list[bytes] = []
    while True:
        chunk = conn.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    line = b"".join(chunks).split(b"\n", 1)[0]
    if not line:
        raise ConnectionError("empty IPC request")
    data = json.loads(line.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("IPC request must be a JSON object")
    return data


def _read_pipe_json_line(pipe: Any) -> dict[str, Any]:
    win32file = importlib.import_module("win32file")

    chunks: list[bytes] = []
    while True:
        _err, chunk = win32file.ReadFile(pipe, 4096)
        chunks.append(bytes(chunk))
        if b"\n" in chunk:
            break
    line = b"".join(chunks).split(b"\n", 1)[0]
    data = json.loads(line.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("IPC request must be a JSON object")
    return data


__all__ = ["IPCServer"]

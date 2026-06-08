"""CLI-side IPC client for prompt preview requests."""

from __future__ import annotations

import importlib
import json
import os
import socket
import time
from pathlib import Path
from typing import Any


def request_preview(
    batch_id: str,
    prompt: str,
    items: list[dict[str, object]],
    timeout: float = 300.0,
    *,
    addr: str | None = None,
) -> dict[str, Any]:
    """Send a prompt-preview request to the GUI and return its response."""

    address = addr or _compute_addr()
    payload: dict[str, object] = {
        "op": "preview",
        "batch_id": batch_id,
        "prompt": prompt,
        "items": items,
    }
    if address.startswith("tcp://"):
        return _request_tcp(address, payload, timeout)
    if os.name == "nt":
        return _request_windows_pipe(address, payload, timeout)
    return _request_unix_socket(address, payload, timeout)


def _compute_addr() -> str:
    if os.name == "nt":
        user = os.environ.get("USERNAME", "user")
        return rf"\\.\pipe\bgs-translator-gui-{user}"
    return str(Path.home() / ".bgs-modding-superpowers" / "translator" / "bgs-translator-gui.sock")


def _request_tcp(address: str, payload: dict[str, object], timeout: float) -> dict[str, Any]:
    host_port = address.removeprefix("tcp://")
    host, port_text = host_port.rsplit(":", 1)
    with socket.create_connection((host, int(port_text)), timeout=timeout) as sock:
        sock.settimeout(timeout)
        _send_json_line(sock, payload)
        return _read_json_line(sock)


def _request_unix_socket(address: str, payload: dict[str, object], timeout: float) -> dict[str, Any]:
    unix_family = socket.AF_UNIX  # type: ignore[attr-defined]
    with socket.socket(unix_family, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(address)
        _send_json_line(sock, payload)
        return _read_json_line(sock)


def _request_windows_pipe(address: str, payload: dict[str, object], timeout: float) -> dict[str, Any]:
    try:
        win32file = importlib.import_module("win32file")
        win32pipe = importlib.import_module("win32pipe")
    except ImportError as exc:
        raise RuntimeError("Windows named-pipe IPC requires pywin32") from exc

    deadline = time.monotonic() + timeout
    while True:
        try:
            handle = win32file.CreateFile(
                address,
                win32file.GENERIC_READ | win32file.GENERIC_WRITE,
                0,
                None,
                win32file.OPEN_EXISTING,
                0,
                None,
            )
            break
        except Exception:
            if time.monotonic() >= deadline:
                raise
            win32pipe.WaitNamedPipe(address, int(min(1000, max(1, (deadline - time.monotonic()) * 1000))))
    try:
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        win32file.WriteFile(handle, data)
        chunks: list[bytes] = []
        while True:
            _err, chunk = win32file.ReadFile(handle, 4096)
            chunks.append(bytes(chunk))
            if b"\n" in chunk:
                break
        line = b"".join(chunks).split(b"\n", 1)[0]
        result = json.loads(line.decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError("IPC response must be a JSON object")
        return result
    finally:
        win32file.CloseHandle(handle)


def _send_json_line(sock: socket.socket, payload: dict[str, object]) -> None:
    sock.sendall((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))


def _read_json_line(sock: socket.socket) -> dict[str, Any]:
    chunks: list[bytes] = []
    while True:
        chunk = sock.recv(4096)
        if not chunk:
            break
        chunks.append(chunk)
        if b"\n" in chunk:
            break
    line = b"".join(chunks).split(b"\n", 1)[0]
    if not line:
        raise ConnectionError("IPC server closed without a response")
    result = json.loads(line.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("IPC response must be a JSON object")
    return result


__all__ = ["request_preview"]

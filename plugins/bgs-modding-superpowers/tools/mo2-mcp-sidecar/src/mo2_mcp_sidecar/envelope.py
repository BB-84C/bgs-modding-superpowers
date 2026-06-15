"""JSON-RPC over stdio envelope for the MO2 MCP sidecar.

Provides register_method() API for later S1b tasks (assets, fomod, archive, install,
world) to register their handlers. Emits {"ready": True} once before processing.
"""
from __future__ import annotations

import json
from typing import Any, Callable, IO

_METHODS: dict[str, Callable[[dict], Any]] = {}


def register_method(name: str, handler: Callable[[dict], Any]) -> None:
    _METHODS[name] = handler


def _error(id_: Any, code: int, message: str) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": code, "message": message}}


def _result(id_: Any, result: Any) -> dict:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def run_stdio_loop(stdin: IO, stdout: IO, stderr: IO, exit_on_eof: bool = False) -> None:
    """JSON-RPC over stdio. Emits {'ready': true} once, then dispatches via _METHODS."""
    stdout.write(json.dumps({"ready": True}) + "\n")
    stdout.flush()

    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            stdout.write(json.dumps(_error(None, -32700, "parse error")) + "\n")
            stdout.flush()
            if exit_on_eof:
                break
            continue

        method = req.get("method")
        params = req.get("params", {})
        id_ = req.get("id")

        handler = _METHODS.get(method)
        if handler is None:
            stdout.write(json.dumps(_error(id_, -32601, f"method not found: {method}")) + "\n")
            stdout.flush()
            if exit_on_eof:
                break
            continue

        try:
            result = handler(params)
            stdout.write(json.dumps(_result(id_, result)) + "\n")
        except Exception as exc:
            stdout.write(json.dumps(_error(id_, -32603, f"{type(exc).__name__}: {exc}")) + "\n")
        stdout.flush()
        if exit_on_eof:
            break

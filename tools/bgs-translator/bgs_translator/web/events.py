"""WebSocket broadcast helpers for the browser control panel."""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketState

_connected_ws: set[WebSocket] = set()


async def connect_ws(ws: WebSocket) -> None:
    """Accept and keep one browser WebSocket connection alive."""

    await ws.accept()
    _connected_ws.add(ws)
    try:
        while True:
            await ws.receive_text()
    except Exception:
        pass
    finally:
        _connected_ws.discard(ws)


async def broadcast_ws(message: dict[str, Any]) -> None:
    """Broadcast a JSON message to all connected browser tabs."""

    dead: list[WebSocket] = []
    for ws in list(_connected_ws):
        if ws.application_state != WebSocketState.CONNECTED:
            dead.append(ws)
            continue
        try:
            await ws.send_json(message)
        except (asyncio.CancelledError, RuntimeError):
            dead.append(ws)
    for ws in dead:
        _connected_ws.discard(ws)


__all__ = ["broadcast_ws", "connect_ws"]

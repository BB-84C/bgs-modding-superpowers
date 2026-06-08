"""IPC server/client prompt-preview protocol tests."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from bgs_translator.core.client import request_preview
from bgs_translator.core.ipc import IPCServer


def test_ipc_server_round_trips_preview_request() -> None:
    seen: list[tuple[str, str, list[dict[str, object]]]] = []

    def callback(batch_id: str, prompt: str, items: list[dict[str, object]]) -> dict[str, str]:
        seen.append((batch_id, prompt, items))
        return {"op": "approved", "prompt": prompt + "\nAPPROVED"}

    server = IPCServer(callback, addr="tcp://127.0.0.1:0")
    server.start()
    try:
        response = request_preview(
            "b1",
            "prompt body",
            [{"item_id": "I1", "source": "Iron Sword"}],
            timeout=2.0,
            addr=server.address,
        )
    finally:
        server.stop()

    assert response == {"op": "approved", "prompt": "prompt body\nAPPROVED"}
    assert seen == [("b1", "prompt body", [{"item_id": "I1", "source": "Iron Sword"}])]


def test_ipc_server_stop_cleans_up_without_hanging() -> None:
    server = IPCServer(lambda _b, prompt, _i: {"op": "approved", "prompt": prompt}, addr="tcp://127.0.0.1:0")

    server.start()
    server.stop()

    assert not server.is_running


def test_ipc_server_handles_multiple_sequential_connections() -> None:
    calls: list[str] = []

    def callback(batch_id: str, prompt: str, _items: list[dict[str, object]]) -> dict[str, str]:
        calls.append(batch_id)
        return {"op": "approved", "prompt": prompt}

    server = IPCServer(callback, addr="tcp://127.0.0.1:0")
    server.start()
    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            responses = list(
                pool.map(
                    lambda index: request_preview(
                        f"b{index}", f"prompt {index}", [], timeout=2.0, addr=server.address
                    ),
                    range(3),
                )
            )
    finally:
        server.stop()

    assert [response["op"] for response in responses] == ["approved", "approved", "approved"]
    assert sorted(calls) == ["b0", "b1", "b2"]

"""HTTP preview client used by CLI workers to talk to the web GUI."""

from __future__ import annotations

from typing import Any

import httpx

from bgs_translator.config import paths
from bgs_translator.core import runtime_pid


def discover_gui() -> tuple[str, str] | None:
    """Return ``(base_url, secret)`` when the web GUI appears alive."""

    alive, _pid = runtime_pid.is_gui_alive()
    if not alive:
        return None
    port_path = paths.translator_root() / "gui.port"
    secret_path = paths.translator_root() / "gui.secret"
    try:
        port = port_path.read_text(encoding="utf-8").strip()
        secret = secret_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not port or not secret:
        return None
    return f"http://127.0.0.1:{port}", secret


def request_preview_http(
    *,
    project: str,
    run_id: str,
    batch_id: str,
    system_prompt: str,
    items: list[dict[str, object]],
    glossary_subset: list[dict[str, object]],
    do_not_translate: list[str],
    timeout: float = 300.0,
) -> dict[str, Any]:
    """Request browser approval for one batch prompt."""

    discovered = discover_gui()
    if discovered is None:
        return {"op": "no_gui"}
    base_url, secret = discovered
    try:
        response = httpx.post(
            f"{base_url}/api/preview/request",
            json={
                "project": project,
                "run_id": run_id,
                "batch_id": batch_id,
                "system_prompt": system_prompt,
                "items": items,
                "glossary_subset": glossary_subset,
                "do_not_translate": do_not_translate,
                "timeout_seconds": timeout,
            },
            headers={"Authorization": f"Bearer {secret}"},
            timeout=timeout + 10.0,
        )
        response.raise_for_status()
        data = response.json()
        return data if isinstance(data, dict) else {"op": "timeout"}
    except (httpx.HTTPError, httpx.TimeoutException):
        return {"op": "timeout"}


__all__ = ["discover_gui", "request_preview_http"]

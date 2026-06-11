"""Cross-process GUI event publishing via per-project sqlite event logs."""

from __future__ import annotations

import logging

import httpx

from bgs_translator.config import paths
from bgs_translator.core.event_queue import GuiEvent
from bgs_translator.core.memory import insert_event, open_memory_db
from bgs_translator.core.runtime_pid import is_gui_alive

log = logging.getLogger(__name__)
_singletons: dict[str, EventPublisher] = {}


class EventPublisher:
    """Durable event publisher: sqlite is truth, HTTP push is notification."""

    def __init__(
        self,
        project: str,
        *,
        gui_url: str | None = None,
        gui_secret: str | None = None,
    ) -> None:
        self.project = project
        self._project_root = paths.project_root(project)
        self._gui_url = gui_url
        self._gui_secret = gui_secret

    def emit(self, event: GuiEvent) -> int | None:
        """Write ``event`` to the project event log and notify the web GUI if alive."""

        if not self._project_root.exists():
            log.debug("Skipping GUI event for missing project root %s", self._project_root)
            return None
        with open_memory_db(self._project_root) as conn:
            event_id = insert_event(conn, event)
        self._push_http(event, event_id)
        return event_id

    def _push_http(self, event: GuiEvent, event_id: int) -> None:
        gui_url, secret = self._resolve_gui()
        if gui_url is None or secret is None:
            return
        payload = {
            "event_id": event_id,
            "project": self.project,
            "kind": event.kind,
            "run_id": event.run_id,
            "batch_id": event.batch_id,
            "payload": event.payload,
            "emitted_at": event.timestamp.isoformat(),
        }
        try:
            httpx.post(
                f"{gui_url}/internal/events",
                json=payload,
                headers={"Authorization": f"Bearer {secret}"},
                timeout=1.0,
            )
        except httpx.HTTPError:
            log.debug("Best-effort GUI event push failed", exc_info=True)

    def _resolve_gui(self) -> tuple[str | None, str | None]:
        if self._gui_url and self._gui_secret:
            return self._gui_url, self._gui_secret
        alive, _pid = is_gui_alive()
        if not alive:
            return None, None
        port_path = paths.translator_root() / "gui.port"
        secret_path = paths.translator_root() / "gui.secret"
        try:
            port = port_path.read_text(encoding="utf-8").strip()
            secret = secret_path.read_text(encoding="utf-8").strip()
        except OSError:
            return None, None
        if not port or not secret:
            return None, None
        return f"http://127.0.0.1:{port}", secret


def get_publisher(project: str) -> EventPublisher:
    """Return one publisher singleton per project name."""

    if project not in _singletons:
        _singletons[project] = EventPublisher(project)
    return _singletons[project]


def reset_publishers_for_tests() -> None:
    """Clear cached publishers for isolated tests."""

    _singletons.clear()


__all__ = ["EventPublisher", "get_publisher", "reset_publishers_for_tests"]

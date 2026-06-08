"""Tk root application for the bgs-translator control panel.

Composes the status bar + nav tree + tab notebook, applies the selected
theme, drives a tiny ``GUI alive`` pulse animation, and routes nav
selection into the active tab.

The application is intentionally non-blocking-safe to construct: callers
may build a ``TranslatorApp`` and ``destroy`` it without ever invoking
``mainloop``. This keeps headless smoke tests cheap.
"""

from __future__ import annotations

import ctypes
import logging
import sys
import threading
import tkinter as tk
import tomllib
from collections.abc import Callable
from pathlib import Path
from tkinter import font as tkfont
from tkinter import ttk
from typing import Any, Final

from bgs_translator.config import paths
from bgs_translator.config.profiles import ProfilesConfig, load_profiles
from bgs_translator.config.settings import Settings, load_settings, update_setting
from bgs_translator.core.event_queue import GuiEvent, get_bridge
from bgs_translator.core.ipc import IPCServer
from bgs_translator.core.runtime_pid import remove_gui_pid, write_gui_pid
from bgs_translator.gui.close_handler import CloseHandler
from bgs_translator.gui.dpi import apply_tk_scaling, enable_windows_dpi_awareness
from bgs_translator.gui.i18n import Translator, set_default_language
from bgs_translator.gui.tabs import (
    BatchesTab,
    EntriesTab,
    GlossaryTab,
    LogsTab,
    ProfilesTab,
    ProjectTab,
    PromptTab,
)
from bgs_translator.gui.themes import apply_theme, get_theme, list_themes
from bgs_translator.gui.widgets import AmberScrollbar, StatusBar
from bgs_translator.gui.widgets.amber_titlebar import AmberTitlebar
from bgs_translator.gui.widgets.resize_handles import ResizeHandles
from bgs_translator.gui.win_chrome import apply_titlebar_tint

log = logging.getLogger(__name__)

_DEFAULT_WIDTH: Final[int] = 1440
_DEFAULT_HEIGHT: Final[int] = 900
_MIN_WIDTH: Final[int] = 1024
_MIN_HEIGHT: Final[int] = 600
# Polish pass 2: nudged up so 'Logs' and 'Glossary' nav nodes are not
# truncated by the Treeview default column width.
_NAV_TREE_WIDTH: Final[int] = 260
_NAV_TREE_COLUMN_WIDTH: Final[int] = 220
_NAV_TREE_COLUMN_MIN_WIDTH: Final[int] = 180

_FONT_PRIORITY: Final[tuple[str, ...]] = (
    "Cascadia Mono",
    "JetBrains Mono",
    "Consolas",
    "Courier New",
)
_FONT_SIZE: Final[int] = 11

_LANGUAGES: Final[list[str]] = ["en", "zh-cn"]

# Visible tab order maps to nav-tree node ids in self._nav_nodes.
_TAB_ORDER: Final[tuple[tuple[str, str], ...]] = (
    ("Project", "project"),
    ("Entries", "entries"),
    ("Batches", "batches"),
    ("Prompt", "prompt"),
    ("Profiles", "profiles"),
    ("Glossary", "glossary"),
    ("Logs", "logs"),
)


def _select_font_family() -> str:
    available = set(tkfont.families())
    for candidate in _FONT_PRIORITY:
        if candidate in available:
            return candidate
    return _FONT_PRIORITY[-1]


def _discover_projects() -> list[str]:
    root = paths.projects_root()
    if not root.exists():
        return []
    names = sorted(
        p.name for p in root.iterdir() if p.is_dir() and (p / "project.toml").exists()
    )
    return names


def _discover_profiles() -> ProfilesConfig:
    try:
        return load_profiles()
    except Exception as exc:
        log.warning("Could not load profiles at startup: %s", exc)
        return ProfilesConfig()


def _safe_load_settings() -> Settings:
    try:
        return load_settings()
    except Exception as exc:
        log.warning("Could not load settings: %s", exc)
        return Settings()


class TranslatorApp(tk.Tk):
    """Tk root window hosting the control panel."""

    def __init__(
        self,
        *,
        theme: str | None = None,
        language: str | None = None,
    ) -> None:
        # DPI awareness must fire before any Tk window exists.
        enable_windows_dpi_awareness()

        super().__init__()

        # Settings + i18n -----------------------------------------------
        self._settings = _safe_load_settings()
        resolved_lang = language or self._settings.ui.language
        resolved_theme = theme or self._settings.ui.theme
        self._translator = Translator(resolved_lang)
        set_default_language(resolved_lang)

        # Window basics -------------------------------------------------
        self.title("bgs-translator control panel")
        self.minsize(_MIN_WIDTH, _MIN_HEIGHT)
        width = max(_MIN_WIDTH, self._settings.ui.window_width or _DEFAULT_WIDTH)
        height = max(_MIN_HEIGHT, self._settings.ui.window_height or _DEFAULT_HEIGHT)
        self.geometry(f"{width}x{height}")

        # Fonts + scaling ----------------------------------------------
        self._font_family = _select_font_family()
        apply_tk_scaling(self)

        # Theme ---------------------------------------------------------
        self._current_theme = resolved_theme
        self._theme_config = get_theme(resolved_theme)
        apply_theme(self, self._theme_config, self._font_family, _FONT_SIZE)

        # Strip native chrome on Windows (iter3). overrideredirect=True
        # removes the OS-drawn titlebar, min/max/close buttons, and
        # window frame entirely; the custom AmberTitlebar takes over.
        # Linux is best-effort (works on most WMs, no shadow). macOS is
        # excluded because overrideredirect drops the rounded corners
        # and shadow; on those hosts the iter2 DWM tint path is the
        # closest we can get without rewriting the chrome entirely.
        self._chrome_stripped = sys.platform in ("win32", "linux")
        if self._chrome_stripped:
            self.withdraw()
            try:
                self.overrideredirect(True)
            except tk.TclError as exc:
                log.debug("overrideredirect rejected by Tk: %s", exc)
                self._chrome_stripped = False

        # Iter2 DWM tint remains useful as a fallback when chrome was
        # not stripped (non-Windows) — apply unconditionally; it
        # silently no-ops on platforms where it does not apply.
        self._titlebar_tint = apply_titlebar_tint(self, self._theme_config)

        # Track amber scrollbars so theme switches can refresh them.
        self._amber_scrollbars: list[AmberScrollbar] = []
        # Track amber checkboxes for the same reason.
        self._amber_checkboxes: list[Any] = []
        self._resize_handles: ResizeHandles | None = None
        self._bridge = get_bridge()
        self._ipc_server = IPCServer(self._handle_preview_request)
        self._drain_after_id: str | None = None
        self._settings_after_id: str | None = None
        self._plan_watcher_stop = threading.Event()
        self._plan_watcher_thread: threading.Thread | None = None
        self._plan_mtimes: dict[Path, float] = {}
        self._nav_visible = True
        self._nav_width = _NAV_TREE_WIDTH
        self._escape_bind_id: str | None = None

        # Close handler -------------------------------------------------
        self._close_handler = CloseHandler(
            self,
            on_force_close=self._on_force_close,
            get_active_project=self._current_project_name,
        )

        # Build UI ------------------------------------------------------
        self._build_layout()
        self._populate_nav()
        self._bind_keyboard_shortcuts()
        self.bind("<Configure>", self._on_configure, add="+")
        self._ipc_server.start()
        write_gui_pid()
        self._start_pulse()
        self._schedule_drain()
        self._start_plan_watcher()

        # Re-show the window. When chrome was stripped we also flip the
        # extended-style bits so the window keeps a taskbar entry —
        # otherwise overrideredirect makes the window a tool window
        # that Windows omits from the taskbar.
        if self._chrome_stripped:
            self._restore_taskbar_visibility()
            self.deiconify()
            try:
                self.lift()
            except tk.TclError:
                pass

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_layout(self) -> None:
        # Outer 1px amber-accent border. When chrome is stripped this
        # gives the window a visible CRT-style edge instead of bleeding
        # into the desktop. When chrome is intact it acts as a thin
        # inset that matches the theme.
        outer_pad = 1 if self._chrome_stripped else 0
        self._outer = tk.Frame(
            self,
            background=self._theme_config.accent,
            padx=outer_pad,
            pady=outer_pad,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
        )
        self._outer.pack(fill="both", expand=True)
        if self._chrome_stripped:
            self._resize_handles = ResizeHandles(
                root=self,
                outer_frame=self._outer,
                theme=self._theme_config,
            )

        # Inner workspace — every other widget lives here so the outer
        # accent stays visible as a clean 1px ring.
        self._workspace = tk.Frame(
            self._outer,
            background=self._theme_config.background,
            borderwidth=0,
            highlightthickness=0,
            relief="flat",
        )
        self._workspace.pack(fill="both", expand=True)
        self._workspace.columnconfigure(0, weight=1)

        next_row = 0
        # Custom titlebar (only when native chrome was stripped).
        self._titlebar: AmberTitlebar | None = None
        if self._chrome_stripped:
            self._titlebar = AmberTitlebar(
                self._workspace,
                self,
                self._theme_config,
                on_close=self._on_titlebar_close,
            )
            self._titlebar.grid(row=next_row, column=0, sticky="ew")
            next_row += 1

        # Status bar.
        self._status_bar = StatusBar(
            self._workspace,
            languages=list(_LANGUAGES),
            themes=list_themes(),
            on_language_change=self._on_language_change,
            on_theme_change=self._on_theme_change,
        )
        self._status_bar.grid(row=next_row, column=0, sticky="ew")
        self._status_bar.set_language(self._translator.language)
        self._status_bar.set_theme(self._current_theme)
        next_row += 1

        # Main paned (nav | content) takes the remaining space.
        self._workspace.rowconfigure(next_row, weight=1)
        self._paned = ttk.PanedWindow(self._workspace, orient="horizontal")
        self._paned.grid(row=next_row, column=0, sticky="nsew", padx=4, pady=(2, 4))

        self._nav_frame = ttk.Frame(self._paned, padding=(4, 4))
        self._paned.add(self._nav_frame, weight=0)
        self._nav_frame.rowconfigure(0, weight=1)
        self._nav_frame.columnconfigure(0, weight=1)

        self._nav_tree = ttk.Treeview(self._nav_frame, show="tree", selectmode="browse")
        # Polish pass 2: widen the implicit '#0' column so descenders in
        # 'Logs', 'Glossary', and 'Profiles' do not get clipped.
        self._nav_tree.column(
            "#0",
            width=_NAV_TREE_COLUMN_WIDTH,
            minwidth=_NAV_TREE_COLUMN_MIN_WIDTH,
            stretch=True,
        )
        nav_scroll = AmberScrollbar(
            self._nav_frame,
            orient="vertical",
            command=self._nav_tree.yview,
            theme_name=self._current_theme,
        )
        self._amber_scrollbars.append(nav_scroll)
        self._nav_tree.configure(yscrollcommand=nav_scroll.set)
        self._nav_tree.grid(row=0, column=0, sticky="nsew")
        nav_scroll.grid(row=0, column=1, sticky="ns")
        self._nav_tree.bind("<<TreeviewSelect>>", self._on_nav_selected)

        # Content frame holds the notebook.
        content_frame = ttk.Frame(self._paned, padding=(4, 4))
        self._paned.add(content_frame, weight=4)
        content_frame.rowconfigure(0, weight=1)
        content_frame.columnconfigure(0, weight=1)

        self._notebook = ttk.Notebook(content_frame)
        self._notebook.grid(row=0, column=0, sticky="nsew")

        self._tabs: dict[str, ttk.Frame] = {}
        for caption, key in _TAB_ORDER:
            tab = self._build_tab(key)
            self._tabs[key] = tab
            self._notebook.add(tab, text=self._translator.gettext(caption))

        # Force a reasonable initial nav width.
        try:
            self._paned.sashpos(0, _NAV_TREE_WIDTH)  # type: ignore[no-untyped-call]
        except tk.TclError:
            pass

    def _bind_keyboard_shortcuts(self) -> None:
        def tab_handler(tab_index: int) -> Callable[[tk.Event[tk.Misc]], str]:
            return lambda _event: self._select_tab_by_index(tab_index)

        for index in range(len(_TAB_ORDER)):
            self.bind(
                f"<Control-Key-{index + 1}>",
                tab_handler(index),
                add="+",
            )
        self.bind("<Control-Key-b>", lambda _event: self._toggle_nav_pane(), add="+")
        self.bind("<Control-Key-B>", lambda _event: self._toggle_nav_pane(), add="+")
        self.bind("<Control-Key-r>", lambda _event: self._refresh_current_project_status(), add="+")
        self.bind("<Control-Key-R>", lambda _event: self._refresh_current_project_status(), add="+")
        self.bind("<Alt-F4>", lambda _event: self._close_handler.request_close(), add="+")
        self._escape_bind_id = self.bind_all(
            "<Escape>",
            lambda _event: self._close_topmost_modal(),
            add="+",
        )

    def _select_tab_by_index(self, index: int) -> str:
        if 0 <= index < len(_TAB_ORDER):
            self._notebook.select(index)  # type: ignore[no-untyped-call]
        return "break"

    def _toggle_nav_pane(self) -> str:
        if self._nav_visible:
            try:
                self._nav_width = int(self._paned.sashpos(0))  # type: ignore[no-untyped-call]
            except tk.TclError:
                self._nav_width = _NAV_TREE_WIDTH
            self._paned.forget(self._nav_frame)
            self._nav_visible = False
            return "break"
        self._paned.insert(0, self._nav_frame, weight=0)
        self._nav_visible = True
        try:
            self._paned.sashpos(0, max(_NAV_TREE_COLUMN_MIN_WIDTH, self._nav_width))  # type: ignore[no-untyped-call]
        except tk.TclError:
            pass
        return "break"

    def _refresh_current_project_status(self) -> str:
        project = self._current_project_name()
        if project:
            self._project_tab.load_project(project)
            self._refresh_cost_from_project(project)
        return "break"

    def _close_topmost_modal(self) -> str:
        grabbed = self.grab_current()  # type: ignore[no-untyped-call]
        if isinstance(grabbed, tk.Toplevel) and grabbed.winfo_exists():
            grabbed.destroy()
            return "break"
        for child in reversed(self.winfo_children()):
            if isinstance(child, tk.Toplevel) and child.winfo_exists():
                child.destroy()
                return "break"
        return "break"

    def _build_tab(self, key: str) -> ttk.Frame:
        if key == "project":
            self._project_tab = ProjectTab(self._notebook)
            if hasattr(self._project_tab, "attach_app"):
                self._project_tab.attach_app(self)
            return self._project_tab
        if key == "profiles":
            self._profiles_tab = ProfilesTab(self._notebook)
            if hasattr(self._profiles_tab, "attach_app"):
                self._profiles_tab.attach_app(self)
            return self._profiles_tab
        if key == "logs":
            self._logs_tab = LogsTab(self._notebook)
            if hasattr(self._logs_tab, "attach_app"):
                self._logs_tab.attach_app(self)
            return self._logs_tab
        if key == "entries":
            tab: ttk.Frame = EntriesTab(
                self._notebook,
                project_root_provider=self.current_project_root,
                theme=self._theme_config,
                gui_event_bridge=self._bridge,
            )
            if hasattr(tab, "attach_app"):
                tab.attach_app(self)
            return tab
        if key == "batches":
            tab = BatchesTab(
                self._notebook,
                project_root_provider=self.current_project_root,
                theme=self._theme_config,
                gui_event_bridge=self._bridge,
            )
            if hasattr(tab, "attach_app"):
                tab.attach_app(self)
            return tab
        if key == "prompt":
            tab = PromptTab(
                self._notebook,
                project_root_provider=self.current_project_root,
                theme=self._current_theme,
                gui_event_bridge=self._bridge,
                ipc_server=self._ipc_server,
            )
            self._prompt_tab = tab
            if hasattr(tab, "attach_app"):
                tab.attach_app(self)
            return tab
        if key == "glossary":
            tab = GlossaryTab(self._notebook)
            if hasattr(tab, "attach_app"):
                tab.attach_app(self)
            return tab
        raise KeyError(f"Unknown tab key: {key}")

    def _populate_nav(self) -> None:
        _ = self._translator.gettext

        self._nav_nodes: dict[str, str] = {}
        projects_node = self._nav_tree.insert("", "end", text=_("Projects"), open=True)
        self._nav_nodes["projects"] = projects_node
        for name in _discover_projects():
            self._nav_tree.insert(projects_node, "end", iid=f"project::{name}", text=name)

        profiles_node = self._nav_tree.insert("", "end", text=_("Profiles"), open=True)
        self._nav_nodes["profiles"] = profiles_node
        profiles_cfg = _discover_profiles()
        active_name = profiles_cfg.active
        for name in sorted(profiles_cfg.profiles.keys()):
            label = f"{name} *" if name == active_name else name
            self._nav_tree.insert(profiles_node, "end", iid=f"profile::{name}", text=label)

        glossary_node = self._nav_tree.insert("", "end", text=_("Glossary"), open=False)
        self._nav_nodes["glossary"] = glossary_node
        for scope in ("vanilla", "mod", "player", "DNT"):
            self._nav_tree.insert(glossary_node, "end", iid=f"glossary::{scope}", text=scope)

        logs_node = self._nav_tree.insert("", "end", text=_("Logs"), open=False)
        self._nav_nodes["logs"] = logs_node
        for bucket in ("today", "yesterday", "older"):
            self._nav_tree.insert(logs_node, "end", iid=f"log::{bucket}", text=bucket)

        self._status_bar.set_profile(active_name or "-")

    # ------------------------------------------------------------------
    # Pulse animation
    # ------------------------------------------------------------------
    def _start_pulse(self) -> None:
        self._pulse_after_id: str | None = None
        self._schedule_pulse()

    def _schedule_pulse(self) -> None:
        self._status_bar.pulse()
        self._pulse_after_id = self.after(400, self._schedule_pulse)

    def _schedule_drain(self) -> None:
        events = self._bridge.drain()
        for event in events:
            self._dispatch_event(event)
        try:
            self._drain_after_id = self.after(50, self._schedule_drain)
        except tk.TclError:
            self._drain_after_id = None

    def _dispatch_event(self, event: GuiEvent) -> None:
        log.debug("GUI event received: %s", event.kind)
        if event.kind == "prompt.preview_request":
            batch_id = event.batch_id or str(event.payload.get("batch_id", ""))
            self._focus_prompt_preview(batch_id)

    def _handle_preview_request(
        self,
        batch_id: str,
        prompt: str,
        items: list[dict[str, object]],
    ) -> dict[str, object]:
        """Synchronous GUI-side prompt preview handler for CLI batch runs.

        The IPC server thread blocks on a per-batch event while the Prompt tab
        renders the prompt and the user decides approve / approve-all / discard.
        """

        payload = {
            "batch_id": batch_id,
            "prompt": prompt,
            "items": items,
            "glossary_subset": [],
            "do_not_translate": [],
        }
        waiter = self._ipc_server._pending_lock
        with waiter:
            event = threading.Event()
            bucket: dict[str, object] = {}
            self._ipc_server._pending[batch_id] = (event, bucket)
        self._bridge.emit(GuiEvent(kind="prompt.preview_request", batch_id=batch_id, payload=payload))
        try:
            self.after(0, lambda: self._focus_prompt_preview(batch_id))
        except tk.TclError:
            pass
        event.wait(timeout=300.0)
        with waiter:
            _pending = self._ipc_server._pending.pop(batch_id, None)
        if not bucket:
            return {"op": "timeout"}
        return dict(bucket)

    def _stop_pulse(self) -> None:
        if self._pulse_after_id is not None:
            try:
                self.after_cancel(self._pulse_after_id)
            except (tk.TclError, ValueError):
                pass
            self._pulse_after_id = None

    def _stop_drain(self) -> None:
        if self._drain_after_id is not None:
            try:
                self.after_cancel(self._drain_after_id)
            except (tk.TclError, ValueError):
                pass
            self._drain_after_id = None

    def _start_plan_watcher(self) -> None:
        if self._plan_watcher_thread is not None:
            return
        self._plan_watcher_thread = threading.Thread(
            target=self._poll_plan_files,
            name="bgs-translator-plan-watcher",
            daemon=True,
        )
        self._plan_watcher_thread.start()

    def _poll_plan_files(self) -> None:
        while not self._plan_watcher_stop.wait(2.0):
            if self._plan_files_changed():
                try:
                    self.after(0, self._reload_prompt_plans_from_watcher)
                except tk.TclError:
                    return

    def _plan_files_changed(self) -> bool:
        project_root = self.current_project_root()
        if project_root is None:
            if self._plan_mtimes:
                self._plan_mtimes = {}
            return False
        current: dict[Path, float] = {}
        for plan_path in (project_root / "batches").glob("*/plan.json"):
            try:
                current[plan_path] = plan_path.stat().st_mtime
            except OSError:
                continue
        changed = current != self._plan_mtimes and bool(self._plan_mtimes or current)
        self._plan_mtimes = current
        return changed

    def _reload_prompt_plans_from_watcher(self) -> None:
        try:
            self._prompt_tab._load_plans()
        except tk.TclError:
            pass

    def _focus_prompt_preview(self, batch_id: str) -> None:
        if not batch_id:
            return
        self._notebook.select(self._prompt_tab)  # type: ignore[no-untyped-call]
        self._prompt_tab.batch_combo.set(batch_id)
        # PromptTab._on_gui_event (drain-time subscriber) already rendered
        # the prompt, side panels, and showed the action row. Do NOT call
        # refresh_for_batch here — render_prompt_for_batch unconditionally
        # hides the action row at its tail, which would race the approve
        # UI back off the screen for live preview events.
        if batch_id not in self._prompt_tab._batch_prompt_by_id:
            # Edge case: event arrived before plan.json was indexed.
            # Fall back to a refresh; action row stays hidden but at least
            # the editor will have the prompt body.
            self._prompt_tab.refresh_for_batch(batch_id)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def _on_nav_selected(self, _event: tk.Event[tk.Misc]) -> None:
        selection = self._nav_tree.selection()
        if not selection:
            return
        iid = selection[0]
        # The custom event is documented in the spec — emit it before
        # routing so external listeners can hook the nav stream.
        try:
            self.event_generate("<<NavSelected>>", when="tail")
        except tk.TclError:
            pass
        if iid.startswith("project::"):
            name = iid.split("::", 1)[1]
            self._project_tab.load_project(name)
            self._notebook.select(self._tabs["project"])  # type: ignore[no-untyped-call]
            self._status_bar.set_project(name)
            self._refresh_cost_from_project(name)
            for key in ("entries", "batches", "prompt", "glossary", "logs"):
                tab = self._tabs.get(key)
                if tab is not None and hasattr(tab, "load_project"):
                    try:
                        tab.load_project(name)
                    except Exception as exc:  # pragma: no cover - defensive UI integration
                        log.debug("%s.load_project failed: %s", key, exc)
        elif iid.startswith("profile::"):
            self._profiles_tab.refresh()
            self._notebook.select(self._tabs["profiles"])  # type: ignore[no-untyped-call]
        elif iid.startswith("glossary::"):
            self._notebook.select(self._tabs["glossary"])  # type: ignore[no-untyped-call]
        elif iid.startswith("log::"):
            self._notebook.select(self._tabs["logs"])  # type: ignore[no-untyped-call]

    def _refresh_cost_from_project(self, name: str) -> None:
        toml_path = paths.project_root(name) / "project.toml"
        if not toml_path.exists():
            return
        try:
            with toml_path.open("rb") as handle:
                data = tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError):
            return
        cost = data.get("cost", {}) if isinstance(data, dict) else {}
        spent = cost.get("spent_usd_session") or cost.get("spent_usd_total") or 0.0
        try:
            self._status_bar.set_cost(float(spent))
        except (TypeError, ValueError):
            pass

    def _on_configure(self, event: tk.Event[tk.Misc]) -> None:
        if event.widget is not self:
            return
        width = int(event.width)
        height = int(event.height)
        if width < _MIN_WIDTH or height < _MIN_HEIGHT:
            return
        if self._settings_after_id is not None:
            try:
                self.after_cancel(self._settings_after_id)
            except (tk.TclError, ValueError):
                pass
        self._settings_after_id = self.after(
            200,
            lambda: self._persist_window_dimensions(width, height),
        )

    def _persist_window_dimensions(self, width: int, height: int) -> None:
        self._settings_after_id = None
        try:
            self._settings = update_setting("ui.window_width", width)
            self._settings = update_setting("ui.window_height", height)
        except (OSError, KeyError, ValueError) as exc:
            log.warning("Could not persist window dimensions: %s", exc)

    def _on_language_change(self, language: str) -> None:
        self._translator.set_language(language)
        set_default_language(language)
        try:
            self._settings = update_setting("ui.language", language)
        except (OSError, KeyError, ValueError) as exc:
            log.warning("Could not persist UI language %s: %s", language, exc)
        # TODO(Chunk-L.2): a full hot reload would tear down and rebuild
        # every cached caption; for MVP we update the visible tab captions
        # plus the status-bar pulse cell and let the rest catch up on
        # the next mount.
        for index, (caption, _key) in enumerate(_TAB_ORDER):
            self._notebook.tab(index, text=self._translator.gettext(caption))  # type: ignore[no-untyped-call]
        log.info("Switched language to %s", language)

    def register_amber_scrollbar(self, scrollbar: AmberScrollbar) -> None:
        """Register a tab-owned scrollbar so theme switches re-tint it."""

        self._amber_scrollbars.append(scrollbar)

    def register_amber_checkbox(self, checkbox: Any) -> None:
        """Register a tab-owned checkbox so theme switches re-tint it."""

        self._amber_checkboxes.append(checkbox)

    def _on_titlebar_close(self) -> None:
        """Route the custom titlebar close click through the close handler."""

        self._close_handler.request_close()

    def _on_theme_change(self, theme: str) -> None:
        self._current_theme = theme
        self._theme_config = get_theme(theme)
        apply_theme(self, self._theme_config, self._font_family, _FONT_SIZE)
        self._titlebar_tint = apply_titlebar_tint(self, self._theme_config)
        if self._titlebar is not None:
            try:
                self._titlebar.apply_theme(self._theme_config)
            except tk.TclError:
                pass
        if self._resize_handles is not None:
            self._resize_handles.apply_theme(self._theme_config)
        # Repaint outer border + workspace to the new accent / bg.
        try:
            self._outer.configure(background=self._theme_config.accent)
            self._workspace.configure(background=self._theme_config.background)
        except tk.TclError:
            pass
        for scrollbar in self._amber_scrollbars:
            try:
                scrollbar.apply_theme(theme)
            except tk.TclError:
                continue
        for checkbox in self._amber_checkboxes:
            try:
                checkbox.apply_theme(theme)
            except tk.TclError:
                continue
        try:
            self._settings = update_setting("ui.theme", theme)
        except (OSError, KeyError, ValueError) as exc:
            log.warning("Could not persist UI theme %s: %s", theme, exc)
        log.info("Switched theme to %s", theme)

    def _restore_taskbar_visibility(self) -> None:
        """Re-enable the Windows taskbar entry after overrideredirect.

        ``overrideredirect(True)`` flips the window into a tool-window
        style that Windows hides from the taskbar. Adding the
        ``WS_EX_APPWINDOW`` bit (and removing ``WS_EX_TOOLWINDOW``)
        puts the entry back.
        """

        if sys.platform != "win32":
            return
        try:
            self.update_idletasks()
            user32: Any = ctypes.windll.user32
            child = int(self.winfo_id())
            hwnd = int(user32.GetAncestor(child, 2)) or child
            GWL_EXSTYLE = -20
            WS_EX_TOOLWINDOW = 0x00000080
            WS_EX_APPWINDOW = 0x00040000
            current = int(user32.GetWindowLongW(hwnd, GWL_EXSTYLE))
            new_style = (current & ~WS_EX_TOOLWINDOW) | WS_EX_APPWINDOW
            user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_style)
        except (OSError, AttributeError, tk.TclError) as exc:
            log.debug("Could not restore taskbar visibility: %s", exc)

    def _on_force_close(self) -> None:
        self._stop_pulse()
        self._stop_drain()
        self._plan_watcher_stop.set()
        if self._settings_after_id is not None:
            try:
                self.after_cancel(self._settings_after_id)
            except (tk.TclError, ValueError):
                pass
            self._settings_after_id = None
        # TODO(Chunk-L.2): cancel in-flight asyncio tasks here when the
        # background runner is wired up.

    def _current_project_name(self) -> str | None:
        project_name = getattr(self._project_tab, "_project_name", None)
        return project_name if isinstance(project_name, str) else None

    def current_project_root(self) -> Path | None:
        """Return the current project root path if a project is selected."""

        project_name = self._current_project_name()
        if not project_name:
            return None
        return paths.project_root(project_name)

    def destroy(self) -> None:
        self._on_force_close()
        try:
            self._ipc_server.stop()
        except Exception:
            pass
        remove_gui_pid()
        if self._escape_bind_id is not None:
            try:
                self.unbind_all("<Escape>")
            except tk.TclError:
                pass
            self._escape_bind_id = None
        super().destroy()

    # Public lifecycle helpers ----------------------------------------
    @property
    def status_bar(self) -> StatusBar:
        return self._status_bar

    @property
    def nav_tree(self) -> ttk.Treeview:
        return self._nav_tree

    @property
    def notebook(self) -> ttk.Notebook:
        return self._notebook

    @property
    def titlebar_tint(self) -> dict[str, bool]:
        """Return the DWM attribute acceptance map from the last apply."""

        return dict(self._titlebar_tint)

    @property
    def chrome_stripped(self) -> bool:
        """Whether ``overrideredirect(True)`` was accepted on this host."""

        return self._chrome_stripped

    @property
    def titlebar(self) -> AmberTitlebar | None:
        """The custom titlebar widget, or ``None`` when chrome is intact."""

        return self._titlebar


def launch(theme: str | None = None, language: str | None = None) -> None:
    """Launch the GUI and block until the user closes the window."""

    app = TranslatorApp(theme=theme, language=language)
    app.mainloop()


__all__ = ["TranslatorApp", "launch"]

"""Prompt preview and approval tab."""

# ruff: noqa: RUF001

from __future__ import annotations

import json
import re
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from typing import Any, Literal, cast

from bgs_translator.config.settings import load_settings, update_setting
from bgs_translator.core.event_queue import EventQueueBridge, GuiEvent, get_bridge
from bgs_translator.gui.i18n import gettext as _
from bgs_translator.gui.themes import get_theme
from bgs_translator.gui.widgets.amber_checkbox import AmberCheckbox
from bgs_translator.gui.widgets.amber_scrollbar import AmberScrollbar
from bgs_translator.gui.widgets.empty_state import EmptyStatePanel
from bgs_translator.pipeline.prompt import load_template, render_prompt

ProjectRootProvider = Callable[[], Path | str | None]


class _LineNumberCanvas(tk.Canvas):
    """Line-number gutter paired with a ``tk.Text`` widget."""

    def __init__(self, master: tk.Misc, text: tk.Text, *, theme_name: str) -> None:
        theme = get_theme(theme_name)
        super().__init__(
            master,
            width=48,
            background=theme.background,
            highlightthickness=0,
            borderwidth=0,
        )
        self._text = text
        self._theme_name = theme_name
        self._fg = theme.dim
        self._font = ("Consolas", 10)

    def redraw(self) -> None:
        """Redraw visible line numbers."""

        self.delete("all")
        index = self._text.index("@0,0")
        while True:
            dline = self._text.dlineinfo(index)
            if dline is None:
                break
            y = int(dline[1])
            line_number = str(index).split(".", 1)[0]
            self.create_text(42, y, anchor="ne", text=line_number, fill=self._fg, font=self._font)
            index = self._text.index(f"{index}+1line")

    def apply_theme(self, theme_name: str) -> None:
        theme = get_theme(theme_name)
        self._theme_name = theme_name
        self._fg = theme.dim
        self.configure(background=theme.background)
        self.redraw()


class PromptTab(ttk.Frame):
    """Canonical GUI surface for prompt preview and approval."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        project_root_provider: ProjectRootProvider | None = None,
        theme: str = "amber",
        gui_event_bridge: EventQueueBridge | None = None,
        ipc_server: Any | None = None,
    ) -> None:
        super().__init__(parent, padding=(12, 12))
        self._get_project_root: ProjectRootProvider = project_root_provider or (lambda: None)
        self._theme_name = theme
        self._theme = get_theme(theme)
        self._event_bridge = gui_event_bridge or get_bridge()
        self._ipc = ipc_server
        self._current_batch_id: str | None = None
        self._editable = tk.BooleanVar(value=False)
        self._edit_scope = tk.StringVar(value="this_batch")
        self._awaiting_approval_callback: Callable[[dict[str, Any]], None] | None = None
        self._batch_prompt_by_id: dict[str, str] = {}
        self._batch_payload_by_id: dict[str, dict[str, Any]] = {}

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        self._build_batch_selector()
        self._build_editor_with_linenos()
        self._build_side_panel()
        self._build_action_row()
        self._empty_state = EmptyStatePanel(
            self._editor_frame,
            caption=_("[ NO PROMPT TO PREVIEW ]"),
            sub_line=_("Run xtl batch plan to assemble a system prompt"),
            theme_name=theme,
        )
        self._empty_state.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0)

        self._unsubscribe = self._event_bridge.subscribe(self._on_gui_event)
        self._load_initial()

    def attach_app(self, app: Any) -> None:
        """Follow-up wiring hook for ``gui/app.py`` without requiring an app edit here."""

        self._app = app
        bridge = getattr(app, "_bridge", None)
        if isinstance(bridge, EventQueueBridge) and bridge is not self._event_bridge:
            self._unsubscribe()
            self._event_bridge = bridge
            self._unsubscribe = self._event_bridge.subscribe(self._on_gui_event)
        register_checkbox = getattr(app, "register_amber_checkbox", None)
        if callable(register_checkbox):
            register_checkbox(self._preview_required_checkbox)

    def destroy(self) -> None:
        try:
            self._unsubscribe()
        except AttributeError:
            pass
        super().destroy()

    def render_prompt_for_batch(self, batch_id: str) -> None:
        """Render a planned batch prompt by id."""

        if batch_id not in self._batch_prompt_by_id:
            self._load_plans()
        prompt = self._batch_prompt_by_id.get(batch_id)
        if prompt is None:
            self._show_empty_state()
            return
        self._current_batch_id = batch_id
        self._batch_var.set(batch_id)
        self._set_editor_text(prompt)
        self._render_side_panel(self._batch_payload_by_id.get(batch_id, {}))
        self._hide_action_row()

    def render_sample_prompt(self, slots: dict[str, object]) -> None:
        """Render a sample prompt with custom slot values."""

        rendered = render_prompt(
            load_template(),
            game_lore_world=str(slots.get("game_lore_world", "Starfield")),
            game_context_lore_summary=str(slots.get("game_context_lore_summary", "")),
            mod_context_name=str(slots.get("mod_context_name", "")),
            mod_context_theme=str(slots.get("mod_context_theme", "")),
            style_directives=str(slots.get("style_directives", "保持语义准确，保留占位符。")),
            glossary_subset_rendered=str(slots.get("glossary_subset_rendered", "")),
            do_not_translate_list=str(slots.get("do_not_translate_list", "")),
            parent_context_summary=_optional_str(slots.get("parent_context_summary")),
            ad_hoc_context=_optional_str(slots.get("ad_hoc_context")),
        )
        self._current_batch_id = None
        self._batch_var.set("next batch")
        self._set_editor_text(rendered)
        self._render_side_panel(
            {
                "glossary_subset": slots.get("glossary_subset", []),
                "do_not_translate": str(slots.get("do_not_translate_list", "")).splitlines(),
            }
        )
        self._hide_action_row()

    def _build_batch_selector(self) -> None:
        top = ttk.Frame(self)
        top.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text=_("Batch"), style="Header.TLabel").grid(row=0, column=0, sticky="w")
        self._batch_var = tk.StringVar(value="next batch")
        self._batch_combo = ttk.Combobox(
            top,
            textvariable=self._batch_var,
            values=("next batch",),
            state="readonly",
            width=32,
        )
        self._batch_combo.grid(row=0, column=1, sticky="ew", padx=(6, 18))
        self._batch_combo.bind("<<ComboboxSelected>>", lambda _event: self.render_prompt_for_batch(self._batch_var.get()))

        self._editable_check = ttk.Checkbutton(
            top,
            text=_("Editable"),
            variable=self._editable,
            command=self._on_editable_toggled,
        )
        self._editable_check.grid(row=0, column=2, sticky="w", padx=(0, 18))
        ttk.Label(top, text=_("Scope"), style="Dim.TLabel").grid(row=0, column=3, sticky="w")
        for offset, (value, label) in enumerate(
            (
                ("this_batch", _("This batch")),
                ("this_sig", _("This sig")),
                ("global", _("Global")),
            ),
            start=4,
        ):
            ttk.Radiobutton(top, text=label, value=value, variable=self._edit_scope).grid(
                row=0,
                column=offset,
                sticky="w",
                padx=(6, 0),
            )

        self._preview_required_checkbox = AmberCheckbox(
            top,
            text=_("Require prompt preview approval before dispatch"),
            initial=self._load_preview_required_setting(),
            command=self._on_preview_required_toggled,
            theme_name=self._theme_name,
        )
        self._preview_required_checkbox.grid(row=1, column=0, columnspan=7, sticky="w", pady=(8, 0))

    def _build_editor_with_linenos(self) -> None:
        self._editor_frame = ttk.Frame(self, style="Surface.TFrame")
        self._editor_frame.grid(row=1, column=0, sticky="nsew")
        self._editor_frame.rowconfigure(0, weight=1)
        self._editor_frame.columnconfigure(1, weight=1)

        self._editor = tk.Text(
            self._editor_frame,
            wrap="none",
            undo=True,
            font=("Consolas", 11),
            state="disabled",
            background=self._theme.surface,
            foreground=self._theme.foreground,
            insertbackground=self._theme.accent,
            selectbackground=self._theme.accent,
            selectforeground=self._theme.accent_fg,
        )
        self._line_numbers = _LineNumberCanvas(self._editor_frame, self._editor, theme_name=self._theme_name)
        y_scroll = AmberScrollbar(
            self._editor_frame,
            orient="vertical",
            command=self._editor.yview,
            theme_name=self._theme_name,
        )
        x_scroll = AmberScrollbar(
            self._editor_frame,
            orient="horizontal",
            command=self._editor.xview,
            theme_name=self._theme_name,
        )
        self._editor.configure(
            yscrollcommand=self._on_editor_yscroll(y_scroll),
            xscrollcommand=x_scroll.set,
        )
        self._line_numbers.grid(row=0, column=0, sticky="ns")
        self._editor.grid(row=0, column=1, sticky="nsew")
        y_scroll.grid(row=0, column=2, sticky="ns")
        x_scroll.grid(row=1, column=1, sticky="ew")
        self._editor.bind("<KeyRelease>", lambda _event: self._after_editor_changed())
        self._editor.bind("<Configure>", lambda _event: self._line_numbers.redraw())
        self._editor.tag_configure("slot", foreground=self._theme.dim)
        self._editor.tag_configure("placeholder", foreground=self._theme.accent)

    def _build_side_panel(self) -> None:
        side = ttk.Frame(self)
        side.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        side.columnconfigure(0, weight=1)
        side.columnconfigure(1, weight=1)

        ttk.Label(side, text=_("Glossary subset"), style="Header.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(side, text=_("DNT list"), style="Header.TLabel").grid(row=0, column=1, sticky="w", padx=(12, 0))
        self._glossary_text = self._make_readonly_side_text(side)
        self._dnt_text = self._make_readonly_side_text(side)
        self._glossary_text.grid(row=1, column=0, sticky="nsew", pady=(3, 0))
        self._dnt_text.grid(row=1, column=1, sticky="nsew", padx=(12, 0), pady=(3, 0))

    def _build_action_row(self) -> None:
        self._action_row = ttk.Frame(self)
        self._action_row.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self._approve_button = ttk.Button(
            self._action_row,
            text=_("Approve and send"),
            style="Accent.TButton",
            command=self._on_approve_send,
        )
        self._approve_all_button = ttk.Button(
            self._action_row,
            text=_("Approve all remaining"),
            command=self._on_approve_remaining,
        )
        self._discard_button = ttk.Button(
            self._action_row,
            text=_("Discard"),
            command=self._on_discard,
        )
        self._approve_button.pack(side="left")
        self._approve_all_button.pack(side="left", padx=(8, 0))
        self._discard_button.pack(side="left", padx=(8, 0))
        self._hide_action_row()

    def _make_readonly_side_text(self, parent: tk.Misc) -> tk.Text:
        text = tk.Text(
            parent,
            height=6,
            wrap="word",
            font=("Consolas", 10),
            state="disabled",
            background=self._theme.surface,
            foreground=self._theme.foreground,
        )
        return text

    def _on_gui_event(self, event: GuiEvent) -> None:
        if cast(str, event.kind) != "prompt.preview_request":
            return
        batch_id = event.batch_id or str(event.payload.get("batch_id", ""))
        prompt = str(event.payload.get("prompt", ""))
        self._current_batch_id = batch_id
        self._batch_prompt_by_id[batch_id] = prompt
        self._batch_payload_by_id[batch_id] = dict(event.payload)
        self._refresh_batch_values()
        self._batch_var.set(batch_id)
        self._set_editor_text(prompt)
        self._render_side_panel(event.payload)
        self._show_action_row()

    def _on_approve_send(self) -> None:
        self._respond_to_preview("approved")

    def _on_approve_remaining(self) -> None:
        self._respond_to_preview("approve_all", approve_all=True)

    def _on_discard(self) -> None:
        self._respond_to_preview("discarded", discard=True)

    def _on_save_edit(self) -> None:
        if self._current_batch_id is not None:
            self._batch_prompt_by_id[self._current_batch_id] = self._editor_text()

    def _respond_to_preview(
        self,
        op: str,
        *,
        approve_all: bool = False,
        discard: bool = False,
    ) -> None:
        if self._current_batch_id is None:
            return
        prompt = self._editor_text()
        if self._ipc is not None and hasattr(self._ipc, "respond"):
            if approve_all:
                self._ipc.respond(self._current_batch_id, op, prompt, approve_all=True)
            elif discard:
                self._ipc.respond(self._current_batch_id, op, prompt, discard=True)
            else:
                self._ipc.respond(self._current_batch_id, op, prompt)
        if self._awaiting_approval_callback is not None:
            self._awaiting_approval_callback({"op": op, "prompt": prompt, "discard": discard})
        self._hide_action_row()

    def _on_editable_toggled(self) -> None:
        self._editor.configure(state="normal" if self._editable.get() else "disabled")

    def _load_preview_required_setting(self) -> bool:
        try:
            return bool(load_settings().behavior.prompt_preview_required)
        except OSError:
            return False

    def _on_preview_required_toggled(self) -> None:
        try:
            update_setting("behavior.prompt_preview_required", self._preview_required_checkbox.value)
        except (OSError, KeyError, ValueError):
            self._preview_required_checkbox.value = self._load_preview_required_setting()

    def _on_editor_yscroll(self, scrollbar: AmberScrollbar) -> Callable[[float | str, float | str], None]:
        def _scroll(first: float | str, last: float | str) -> None:
            scrollbar.set(first, last)
            self._line_numbers.redraw()

        return _scroll

    def _after_editor_changed(self) -> None:
        self._highlight_prompt_tokens()
        self._line_numbers.redraw()

    def _set_editor_text(self, text: str) -> None:
        old_state = str(self._editor.cget("state"))
        self._editor.configure(state="normal")
        self._editor.delete("1.0", "end")
        self._editor.insert("1.0", text)
        restored_state: Literal["normal", "disabled"] = "normal" if old_state == "normal" else "disabled"
        self._editor.configure(state=restored_state)
        self._empty_state.place_forget()
        self._highlight_prompt_tokens()
        self._line_numbers.redraw()

    def _editor_text(self) -> str:
        return self._editor.get("1.0", "end-1c")

    def _highlight_prompt_tokens(self) -> None:
        self._editor.tag_remove("slot", "1.0", "end")
        self._editor.tag_remove("placeholder", "1.0", "end")
        text = self._editor_text()
        for match in re.finditer(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}", text):
            self._tag_span("slot", match.start(), match.end())
        for match in re.finditer(r"\{\{P\d+\}\}", text):
            self._tag_span("placeholder", match.start(), match.end())

    def _tag_span(self, tag: str, start: int, end: int) -> None:
        self._editor.tag_add(tag, f"1.0+{start}c", f"1.0+{end}c")

    def _render_side_panel(self, payload: dict[str, Any]) -> None:
        glossary_lines = [_format_glossary_entry(item) for item in _as_list(payload.get("glossary_subset"))]
        dnt_lines = [f"- {item}" for item in _as_list(payload.get("do_not_translate")) if str(item)]
        self._set_text(self._glossary_text, "\n".join(line for line in glossary_lines if line))
        self._set_text(self._dnt_text, "\n".join(dnt_lines))

    def _set_text(self, widget: tk.Text, body: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", body)
        widget.configure(state="disabled")

    def _load_initial(self) -> None:
        self._load_plans()
        if self._batch_prompt_by_id:
            self.render_prompt_for_batch(next(iter(self._batch_prompt_by_id)))
        else:
            self._show_empty_state()

    def _load_plans(self) -> None:
        root_value = self._get_project_root()
        if root_value is None:
            return
        project_root = Path(root_value)
        for plan_path in sorted((project_root / "batches").glob("*/plan.json")):
            try:
                data = json.loads(plan_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            sample_prompt = str(data.get("sample_system_prompt", ""))
            for batch in data.get("batches", []):
                if not isinstance(batch, dict):
                    continue
                batch_id = str(batch.get("batch_id", ""))
                if not batch_id:
                    continue
                prompt = sample_prompt
                parent = batch.get("parent_context_summary")
                if parent:
                    prompt = f"{sample_prompt}\n\n{parent}"
                self._batch_prompt_by_id[batch_id] = prompt
                self._batch_payload_by_id[batch_id] = batch
        self._refresh_batch_values()

    def _refresh_batch_values(self) -> None:
        values = tuple(self._batch_prompt_by_id.keys()) or ("next batch",)
        self._batch_combo.configure(values=values)

    def _show_empty_state(self) -> None:
        self._set_editor_text("")
        self._empty_state.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0)
        self._set_text(self._glossary_text, "")
        self._set_text(self._dnt_text, "")
        self._hide_action_row()

    def _show_action_row(self) -> None:
        self._action_row.grid()

    def _hide_action_row(self) -> None:
        self._action_row.grid_remove()


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text or None


def _as_list(value: object) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value is None:
        return []
    return [value]


def _format_glossary_entry(entry: object) -> str:
    if isinstance(entry, dict):
        source = str(entry.get("source", ""))
        target = str(entry.get("target", ""))
        category = str(entry.get("category", ""))
        confidence = str(entry.get("confidence", ""))
    else:
        source = str(getattr(entry, "source", ""))
        target = str(getattr(entry, "target", ""))
        category = str(getattr(entry, "category", ""))
        confidence = str(getattr(entry, "confidence", ""))
    if not source and not target:
        return ""
    meta = ", ".join(part for part in (category, confidence) if part)
    suffix = f" ({meta})" if meta else ""
    return f"- {source} → {target}{suffix}"


__all__ = ["PromptTab"]
